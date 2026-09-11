"""
SQLite setup for SahakarSetu.

One file-based database, no ORM. The path comes from the SAHAKARSETU_DB
environment variable and defaults to sahakarsetu.db in the project root.
Tests point DB_PATH at a temporary file, so every function here reads
DB_PATH at call time instead of capturing it at import.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("SAHAKARSETU_DB", BASE_DIR / "sahakarsetu.db"))

log = logging.getLogger("sahakarsetu.database")

BOOKING_STATUSES: tuple[str, ...] = ("pending", "assigned", "completed", "cancelled")

# Core tables. The booking flow (app/booking_flow_db.py) adds its own tables
# and columns on top of these on first use; nothing here is ever dropped.
SCHEMA = """
CREATE TABLE IF NOT EXISTS workers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    phone           TEXT,
    trade           TEXT    NOT NULL,
    latitude        REAL    NOT NULL,
    longitude       REAL    NOT NULL,
    jobs_this_week  INTEGER NOT NULL DEFAULT 0 CHECK (jobs_this_week >= 0),
    rating          REAL    CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),  -- NULL until first rating
    availability    TEXT    NOT NULL DEFAULT '[]', -- JSON list of AvailabilityWindow
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name   TEXT    NOT NULL,
    customer_phone  TEXT,
    trade           TEXT    NOT NULL,
    latitude        REAL    NOT NULL,
    longitude       REAL    NOT NULL,
    address         TEXT,
    scheduled_for   TEXT,                          -- ISO 8601, NULL = as soon as possible
    status          TEXT    NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'assigned', 'completed', 'cancelled')),
    customer_user_id INTEGER REFERENCES users(id), -- the Ghar account that placed it (NULL for legacy rows)
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id      INTEGER NOT NULL UNIQUE REFERENCES bookings(id),   -- one assignment per booking
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    score           REAL,                          -- allocation engine score, 0..1
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Accounts are per portal: the same phone may hold one Ghar, one Kaam and one
-- Sabha account, and a session only ever opens the portal it was created for.
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    portal          TEXT    NOT NULL CHECK (portal IN ('ghar', 'kaam', 'sabha')),
    phone           TEXT    NOT NULL,              -- 10 digits, normalised
    name            TEXT    NOT NULL,
    password_hash   TEXT    NOT NULL,
    locality        TEXT,                          -- ghar, kaam
    role            TEXT,                          -- sabha: secretary, member, ...
    worker_id       INTEGER REFERENCES workers(id),-- kaam: the worker record this account drives
    languages       TEXT    NOT NULL DEFAULT '[]', -- JSON list, e.g. ["hi", "en"]
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (portal, phone)
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash      TEXT    PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version         INTEGER PRIMARY KEY,
    applied_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workers_trade        ON workers (trade);
CREATE INDEX IF NOT EXISTS idx_sessions_user        ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status      ON bookings (status);
CREATE INDEX IF NOT EXISTS idx_bookings_trade       ON bookings (trade);
CREATE INDEX IF NOT EXISTS idx_assignments_booking  ON assignments (booking_id);
CREATE INDEX IF NOT EXISTS idx_assignments_worker   ON assignments (worker_id);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection with row access by column name and foreign keys on."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    # WAL lets dashboard polling continue while a booking transaction writes.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Connection for one unit of work: commits on success, rolls back on error, always closes."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migration_1_customer_owner(conn: sqlite3.Connection) -> None:
    """bookings.customer_user_id for databases created before accounts existed."""
    if "customer_user_id" not in _columns(conn, "bookings"):
        conn.execute("ALTER TABLE bookings ADD COLUMN customer_user_id INTEGER REFERENCES users(id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_customer ON bookings (customer_user_id)")


def _migration_2_integrity_triggers(conn: sqlite3.Connection) -> None:
    """Integrity rules for databases whose tables predate the CHECK constraints.

    SQLite cannot add a CHECK to an existing table without rebuilding it, so
    the same rules are enforced with triggers; they are harmless on a fresh
    database where the CHECKs already exist. Existing rows are never altered
    or removed: rows that break a rule are reported so an operator can fix
    them, and the rule applies to every write from now on.
    """
    statuses = ", ".join(f"'{status}'" for status in BOOKING_STATUSES)
    rules = {
        "trg_bookings_status": (
            "bookings", f"NEW.status NOT IN ({statuses})",
            "booking status must be pending, assigned, completed or cancelled",
        ),
        "trg_workers_jobs": ("workers", "NEW.jobs_this_week < 0", "jobs_this_week must be 0 or more"),
        "trg_workers_rating": (
            "workers", "NEW.rating IS NOT NULL AND (NEW.rating < 1 OR NEW.rating > 5)",
            "rating must be between 1 and 5",
        ),
    }
    for name, (table, bad_when, message) in rules.items():
        for event in ("INSERT", "UPDATE"):
            conn.execute(
                f"CREATE TRIGGER IF NOT EXISTS {name}_{event.lower()} BEFORE {event} ON {table} "
                f"WHEN {bad_when} BEGIN SELECT RAISE(ABORT, '{message}'); END"
            )
    # one assignment per booking, even where a legacy table has no UNIQUE constraint
    conn.execute(
        "CREATE TRIGGER IF NOT EXISTS trg_assignments_unique_insert BEFORE INSERT ON assignments "
        "WHEN EXISTS (SELECT 1 FROM assignments WHERE booking_id = NEW.booking_id) "
        "BEGIN SELECT RAISE(ABORT, 'booking already has an assignment'); END"
    )
    duplicates = conn.execute(
        "SELECT booking_id, COUNT(*) AS n FROM assignments GROUP BY booking_id HAVING n > 1"
    ).fetchall()
    if duplicates:
        log.warning("assignments has %d bookings with more than one assignment (kept as-is): %s",
                    len(duplicates), [row["booking_id"] for row in duplicates])
    else:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_booking_unique ON assignments (booking_id)")
    for table, condition, what in (
        ("bookings", f"status NOT IN ({statuses})", "an unknown status"),
        ("workers", "jobs_this_week < 0", "a negative jobs_this_week"),
        ("workers", "rating IS NOT NULL AND (rating < 1 OR rating > 5)", "a rating outside 1..5"),
    ):
        bad = [row["id"] for row in conn.execute(f"SELECT id FROM {table} WHERE {condition}")]
        if bad:
            log.warning("%s rows with %s (left unchanged, please review): %s", table, what, bad)


MIGRATIONS = (
    (1, _migration_1_customer_owner),
    (2, _migration_2_integrity_triggers),
)


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Apply any migrations not yet recorded in schema_migrations. Additive only; returns the versions applied."""
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    done: list[int] = []
    for version, step in MIGRATIONS:
        if version in applied:
            continue
        step(conn)
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        done.append(version)
    if done:
        log.info("applied database migrations %s", done)
    return done


def init_db() -> None:
    """Create the core tables if they do not exist and bring older databases up to date. Safe to call repeatedly."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.executescript(SCHEMA)
        migrate(conn)
