"""
Database plumbing for the booking flow endpoints.

- Opens connections to the SQLite file already configured in app/database.py
  (no second database is created).
- Provides an all-or-nothing transaction helper.
- Adds the few tables/columns the new endpoints need, idempotently.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app import database

# Names looked up in app/database.py, in this order.
_PATH_ATTRIBUTES = ("DB_PATH", "DATABASE_PATH", "SQLITE_PATH", "DB_FILE", "DATABASE_FILE")
_CONNECTION_FACTORIES = ("get_connection", "get_conn", "connect", "get_db_connection")

# Column-name candidates for existing tables whose exact spelling may differ.
ASSIGNMENT_SCORE_COLUMNS = ("score", "allocation_score", "total_score", "final_score")
WORKER_NAME_COLUMNS = ("name", "full_name", "worker_name")
WORKER_RATING_COLUMNS = ("rating", "avg_rating", "average_rating")

_NEW_TABLES = {
    "payment_ledger": """
        CREATE TABLE payment_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL REFERENCES bookings(id),
            worker_id INTEGER REFERENCES workers(id),
            party TEXT NOT NULL CHECK (party IN ('worker', 'welfare_fund', 'platform_operations')),
            share_percent INTEGER NOT NULL,
            amount_paise INTEGER NOT NULL CHECK (amount_paise >= 0),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (booking_id, party)
        )
    """,
    "booking_ratings": """
        CREATE TABLE booking_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
            worker_id INTEGER NOT NULL REFERENCES workers(id),
            rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
}
_NEW_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_payment_ledger_worker ON payment_ledger (worker_id)",
    "CREATE INDEX IF NOT EXISTS idx_booking_ratings_worker ON booking_ratings (worker_id)",
)


def _database_path() -> str | None:
    for attr in _PATH_ATTRIBUTES:
        value = getattr(database, attr, None)
        if value:
            return str(value)
    return None


def open_connection() -> sqlite3.Connection:
    """Open a fresh connection to the project's SQLite database.

    The booking flow manages its own transactions, so it prefers opening its
    own connection from the configured path and only falls back to the
    project's connection function.
    """
    path = _database_path()
    conn: sqlite3.Connection | None = None
    if path is not None:
        conn = sqlite3.connect(path, timeout=30)
    else:
        for name in _CONNECTION_FACTORIES:
            factory = getattr(database, name, None)
            if callable(factory):
                candidate = factory()
                if isinstance(candidate, sqlite3.Connection):
                    conn = candidate
                    break
    if conn is None:
        raise RuntimeError(
            "Could not locate the SQLite database. Expose a path "
            f"({', '.join(_PATH_ATTRIBUTES)}) or a connection function "
            f"({', '.join(_CONNECTION_FACTORIES)}) in app/database.py."
        )

    conn.row_factory = sqlite3.Row
    # Transactions are issued explicitly below, so turn off the sqlite3
    # module's implicit BEGINs (works for both Python 3.12 transaction modes).
    if getattr(conn, "autocommit", None) is False:
        conn.autocommit = True
    else:
        conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def immediate_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """All-or-nothing block.

    BEGIN IMMEDIATE takes SQLite's write lock before any reads, so two
    requests can never both see a booking as 'pending' and assign it twice.
    Any exception inside the block rolls every change back.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def pick_column(conn: sqlite3.Connection, table: str, candidates: tuple[str, ...]) -> str | None:
    columns = table_columns(conn, table)
    return next((c for c in candidates if c in columns), None)


def _pending_changes(conn: sqlite3.Connection) -> list[str]:
    statements: list[str] = []
    existing_tables = {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = [t for t in ("workers", "bookings", "assignments") if t not in existing_tables]
    if missing:
        raise RuntimeError(
            f"Expected existing tables {missing} in the SQLite database. "
            "Run the project's database setup before using the booking flow."
        )

    for table, ddl in _NEW_TABLES.items():
        if table not in existing_tables:
            statements.append(ddl)

    assignment_cols = table_columns(conn, "assignments")
    for required in ("booking_id", "worker_id"):
        if required not in assignment_cols:
            raise RuntimeError(f"assignments table has no '{required}' column.")
    if not any(c in assignment_cols for c in ASSIGNMENT_SCORE_COLUMNS):
        statements.append("ALTER TABLE assignments ADD COLUMN allocation_score REAL")
    if "score_breakdown" not in assignment_cols:
        statements.append("ALTER TABLE assignments ADD COLUMN score_breakdown TEXT")
    if "explanation" not in assignment_cols:
        statements.append("ALTER TABLE assignments ADD COLUMN explanation TEXT")

    booking_cols = table_columns(conn, "bookings")
    if "status" not in booking_cols:
        raise RuntimeError("bookings table has no 'status' column.")
    if "completed_at" not in booking_cols:
        statements.append("ALTER TABLE bookings ADD COLUMN completed_at TEXT")

    worker_cols = table_columns(conn, "workers")
    if "jobs_this_week" not in worker_cols:
        raise RuntimeError("workers table has no 'jobs_this_week' column.")
    if any(c in worker_cols for c in WORKER_RATING_COLUMNS):
        if "base_rating" not in worker_cols:
            statements.append("ALTER TABLE workers ADD COLUMN base_rating REAL")
        if "rating_count" not in worker_cols:
            statements.append("ALTER TABLE workers ADD COLUMN rating_count INTEGER NOT NULL DEFAULT 0")
    return statements


def ensure_booking_flow_schema(conn: sqlite3.Connection) -> None:
    """Add the booking-flow tables and columns if they are missing. Safe to call on every request."""
    if not _pending_changes(conn):
        return
    with immediate_transaction(conn):
        # Re-check under the write lock in case another request just applied them.
        for statement in _pending_changes(conn):
            conn.execute(statement)
        for statement in _NEW_INDEXES:
            conn.execute(statement)


@contextmanager
def booking_flow_connection() -> Iterator[sqlite3.Connection]:
    """Connection for one request: opened, schema-checked, always closed."""
    conn = open_connection()
    try:
        ensure_booking_flow_schema(conn)
        yield conn
    finally:
        conn.close()
