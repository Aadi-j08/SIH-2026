"""
Database setup for SahakarSetu.

Supports Cloud PostgreSQL (Neon.tech / Supabase / Render) in production via DATABASE_URL,
with SQLite + WAL fallback for local development and lightning-fast unit tests.
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
DATABASE_URL = os.environ.get("DATABASE_URL")

# Postgres (Neon) when DATABASE_URL says so, SQLite otherwise. Read through the
# module attribute at call time so tests can monkeypatch it off.
def use_postgres() -> bool:
    url = globals().get("DATABASE_URL") or ""
    return url.startswith(("postgres://", "postgresql://"))

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
    status          TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active')),  -- pending = awaiting council approval
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- which member cooperative owns this worker
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
                    CHECK (status IN ('pending', 'assigned', 'in_progress', 'completed', 'cancelled')),
    urgency_level   TEXT    NOT NULL DEFAULT 'medium'
                    CHECK (urgency_level IN ('low', 'medium', 'high', 'urgent')),
    customer_user_id INTEGER REFERENCES users(id), -- the Ghar account that placed it (NULL for legacy rows)
    cooperative_id   INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- member cooperative that owns this booking
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id      INTEGER NOT NULL UNIQUE REFERENCES bookings(id),   -- one assignment per booking
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    score           REAL,                          -- allocation engine score, 0..1
    accepted_at     TEXT,                          -- when the worker tapped Accept (NULL = not yet)
    started_at      TEXT,                          -- when work was started (after selfie)
    start_selfie_url TEXT,                         -- proof-of-work arrival selfie
    end_photo_url   TEXT,                          -- proof-of-work completion photo
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- member cooperative that owns this assignment
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- A worker passing a job on. The assignment row is removed and the booking goes
-- back to pending (then straight to the next-best worker); this keeps the record.
CREATE TABLE IF NOT EXISTS declines (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id      INTEGER NOT NULL REFERENCES bookings(id),
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    reason          TEXT    NOT NULL CHECK (reason IN ('unwell', 'too_far', 'already_booked', 'not_my_job', 'other')),
    note            TEXT,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- member cooperative that owns this decline
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
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- member cooperative this account belongs to
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (portal, phone)
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash      TEXT    PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- cooperative the session was issued under
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at      TEXT    NOT NULL
);

-- The federation: one row per member cooperative. The default row (id = 1)
-- is the original cooperative and is backfilled/seeded on first use so that
-- single-cooperative deployments keep working unchanged (see app/tenancy.py).
CREATE TABLE IF NOT EXISTS cooperative_federations (
    id                INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL,
    code              TEXT    NOT NULL UNIQUE,           -- short identifier, e.g. "SABHA-2026"
    region            TEXT,
    short_name        TEXT    NOT NULL,
    registration_id   TEXT,
    established       INTEGER,
    area              TEXT,
    radius_km         REAL,
    verified          INTEGER NOT NULL DEFAULT 0,
    worker_kyc        INTEGER NOT NULL DEFAULT 0,
    payments_verified INTEGER NOT NULL DEFAULT 0,
    secretary         TEXT,
    coordinator       TEXT,
    last_meeting      TEXT,                              -- ISO date
    weekly_job_limit  INTEGER NOT NULL DEFAULT 6 CHECK (weekly_job_limit > 0),
    fund_allocation   TEXT    NOT NULL DEFAULT '{}',    -- JSON {category: percent}, sums to 100
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Disputes: raised by a customer or worker on a booking, mediated by the council.
CREATE TABLE IF NOT EXISTS disputes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id        INTEGER NOT NULL REFERENCES bookings(id),
    kind              TEXT    NOT NULL CHECK (kind IN ('payment', 'quality', 'other')),
    raised_by         TEXT    NOT NULL CHECK (raised_by IN ('customer', 'worker', 'council')),
    raised_by_user_id INTEGER REFERENCES users(id),
    amount_paise      INTEGER CHECK (amount_paise IS NULL OR amount_paise >= 0),
    description       TEXT,
    status            TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    resolution        TEXT,
    cooperative_id     INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- member cooperative this dispute belongs to
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at       TEXT
);

-- Community rate card: the standard price of an hour of each trade, fixed by the general body.
-- A settlement quotes from it; the agreed amount may sit within a fair band around it.
CREATE TABLE IF NOT EXISTS standard_rates (
    trade              TEXT    NOT NULL,
    cooperative_id     INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- member cooperative that owns this rate card row
    visit_charge_paise INTEGER NOT NULL CHECK (visit_charge_paise >= 0),
    hourly_rate_paise  INTEGER NOT NULL CHECK (hourly_rate_paise > 0),
    min_hours          REAL    NOT NULL DEFAULT 1 CHECK (min_hours > 0),
    band_percent       INTEGER NOT NULL DEFAULT 25 CHECK (band_percent BETWEEN 0 AND 100),
    note               TEXT,
    updated_at         TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trade, cooperative_id)
);

-- Settlement: the price of a finished job, agreed by the worker and the customer.
-- The worker proposes hours + materials against the rate card; the customer agrees,
-- counters, or asks the council. Once agreed the booking completes and the ledger
-- splits the amount. Money itself is paid customer -> worker directly; nothing here is a payment.
CREATE TABLE IF NOT EXISTS settlements (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id        INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
    worker_id         INTEGER NOT NULL REFERENCES workers(id),
    hours_worked      REAL    NOT NULL CHECK (hours_worked > 0),
    materials_paise   INTEGER NOT NULL DEFAULT 0 CHECK (materials_paise >= 0),
    work_note         TEXT,
    standard_paise    INTEGER NOT NULL CHECK (standard_paise >= 0),
    proposed_paise    INTEGER NOT NULL CHECK (proposed_paise > 0),
    counter_paise     INTEGER CHECK (counter_paise IS NULL OR counter_paise > 0),
    customer_note     TEXT,
    agreed_paise      INTEGER CHECK (agreed_paise IS NULL OR agreed_paise > 0),
    status            TEXT    NOT NULL DEFAULT 'proposed'
                      CHECK (status IN ('proposed', 'countered', 'agreed', 'disputed')),
    paid_via          TEXT    CHECK (paid_via IS NULL OR paid_via IN ('cash', 'upi', 'other')),
    dispute_id        INTEGER REFERENCES disputes(id),
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at      TEXT,
    agreed_at         TEXT,
    cooperative_id     INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id) -- member cooperative this settlement belongs to
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version         INTEGER PRIMARY KEY,
    applied_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workers_trade        ON workers (trade);
CREATE INDEX IF NOT EXISTS idx_sessions_user        ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_disputes_status      ON disputes (status);
CREATE INDEX IF NOT EXISTS idx_bookings_status      ON bookings (status);
CREATE INDEX IF NOT EXISTS idx_bookings_trade       ON bookings (trade);
CREATE INDEX IF NOT EXISTS idx_assignments_booking  ON assignments (booking_id);
CREATE INDEX IF NOT EXISTS idx_assignments_worker   ON assignments (worker_id);
CREATE INDEX IF NOT EXISTS idx_declines_booking     ON declines (booking_id);
CREATE INDEX IF NOT EXISTS idx_declines_worker     ON declines (worker_id);

CREATE TABLE IF NOT EXISTS feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT    NOT NULL CHECK (type IN ('bug', 'feature', 'general')),
    rating          INTEGER CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    message         TEXT    NOT NULL,
    user_id         INTEGER REFERENCES users(id),
    user_name       TEXT,
    user_phone      TEXT,
    user_portal     TEXT CHECK (user_portal IN ('ghar', 'kaam', 'sabha')),
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id), -- member cooperative this feedback belongs to
    resolved        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_type    ON feedback (type);
CREATE INDEX IF NOT EXISTS idx_feedback_user    ON feedback (user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_resolved ON feedback (resolved);

-- ── Phase B: provider profile (skills, certificates, portfolio, documents) ──
CREATE TABLE IF NOT EXISTS worker_skills (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    skill           TEXT    NOT NULL,
    level           TEXT    NOT NULL DEFAULT 'intermediate'
                    CHECK (level IN ('beginner', 'intermediate', 'expert')),
    verified        INTEGER NOT NULL DEFAULT 0,
    verified_by     INTEGER REFERENCES users(id),         -- council user who approved
    verified_at     TEXT,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (worker_id, skill)
);

CREATE TABLE IF NOT EXISTS certifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    name            TEXT    NOT NULL,
    issuing_org     TEXT,
    issue_date      TEXT,                                 -- ISO date
    expiry_date     TEXT,                                 -- ISO date, NULL = no expiry
    document        TEXT,                                 -- file path / URL of the certificate (stored off-FS)
    verified        INTEGER NOT NULL DEFAULT 0,
    verified_by     INTEGER REFERENCES users(id),
    verified_at     TEXT,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (worker_id, name, issuing_org, issue_date)
);

CREATE TABLE IF NOT EXISTS portfolio_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    image_url       TEXT    NOT NULL,                    -- off-FS storage reference
    caption         TEXT,
    category        TEXT,                                 -- e.g. 'before','after','work_in_progress'
    verified        INTEGER NOT NULL DEFAULT 0,
    verified_by     INTEGER REFERENCES users(id),
    verified_at     TEXT,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS worker_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    document_type   TEXT    NOT NULL,                     -- e.g. 'id_proof','insurance','vehicle','other'
    file_url        TEXT    NOT NULL,                    -- off-FS storage reference
    uploaded_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    UNIQUE (worker_id, document_type, file_url)
);

CREATE INDEX IF NOT EXISTS idx_worker_skills_worker    ON worker_skills (worker_id);
CREATE INDEX IF NOT EXISTS idx_worker_skills_coop      ON worker_skills (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_certifications_worker   ON certifications (worker_id);
CREATE INDEX IF NOT EXISTS idx_certifications_coop     ON certifications (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_certifications_verified ON certifications (verified);
CREATE INDEX IF NOT EXISTS idx_portfolio_worker        ON portfolio_items (worker_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_coop          ON portfolio_items (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_worker_documents_worker  ON worker_documents (worker_id);
CREATE INDEX IF NOT EXISTS idx_worker_documents_coop    ON worker_documents (cooperative_id);

-- ── Phase E: welfare benefits, insurance policies and grievances ─────────
CREATE TABLE IF NOT EXISTS benefits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    kind            TEXT    NOT NULL CHECK (kind IN ('pension', 'medical', 'disability', 'other')),
    name            TEXT    NOT NULL,
    description     TEXT,
    eligible        INTEGER NOT NULL DEFAULT 0,          -- whether the worker currently qualifies
    claimed         INTEGER NOT NULL DEFAULT 0,
    amount_rupees   REAL    CHECK (amount_rupees IS NULL OR amount_rupees >= 0),
    start_date      TEXT,
    end_date        TEXT,
    document        TEXT,                                 -- off-FS proof/reference
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS insurance_policies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    kind            TEXT    NOT NULL CHECK (kind IN ('health', 'accident', 'life', 'liability', 'other')),
    insurer         TEXT,
    policy_number   TEXT,
    premium_rupees  REAL    NOT NULL CHECK (premium_rupees >= 0),
    premium_paid    INTEGER NOT NULL DEFAULT 0,
    coverage_paise  INTEGER NOT NULL CHECK (coverage_paise >= 0),
    start_date      TEXT,
    end_date        TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS grievances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id       INTEGER REFERENCES workers(id),
    raised_by_user_id INTEGER REFERENCES users(id),
    kind            TEXT    NOT NULL CHECK (kind IN ('wage', 'safety', 'equipment', 'assignment', 'other')),
    title           TEXT    NOT NULL,
    description     TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'triaged', 'in_progress', 'resolved', 'rejected')),
    resolution      TEXT,
    priority        TEXT    NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
    cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_benefits_worker     ON benefits (worker_id);
CREATE INDEX IF NOT EXISTS idx_benefits_coop       ON benefits (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_insurance_coop      ON insurance_policies (cooperative_id);
CREATE INDEX IF NOT EXISTS idx_insurance_active    ON insurance_policies (active);
CREATE INDEX IF NOT EXISTS idx_grievances_worker   ON grievances (worker_id);
CREATE INDEX IF NOT EXISTS idx_grievances_status   ON grievances (status);
CREATE INDEX IF NOT EXISTS idx_grievances_coop     ON grievances (cooperative_id);
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


def _migration_3_worker_status_and_replies(conn: sqlite3.Connection) -> None:
    """workers.status (existing workers stay active) and assignments.accepted_at for databases
    created before council approval and job replies existed. The declines table is in SCHEMA."""
    if "status" not in _columns(conn, "workers"):
        conn.execute("ALTER TABLE workers ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
        for event in ("INSERT", "UPDATE"):
            conn.execute(
                f"CREATE TRIGGER IF NOT EXISTS trg_workers_status_{event.lower()} BEFORE {event} ON workers "
                "WHEN NEW.status NOT IN ('pending', 'active') "
                "BEGIN SELECT RAISE(ABORT, 'worker status must be pending or active'); END"
            )
    if "accepted_at" not in _columns(conn, "assignments"):
        conn.execute("ALTER TABLE assignments ADD COLUMN accepted_at TEXT")


def _migration_4_urgency_and_proof_of_work(conn: sqlite3.Connection) -> None:
    """Adds bookings.urgency_level and assignments proof-of-work columns."""
    if "urgency_level" not in _columns(conn, "bookings"):
        conn.execute("ALTER TABLE bookings ADD COLUMN urgency_level TEXT NOT NULL DEFAULT 'medium'")
    if "start_selfie_url" not in _columns(conn, "assignments"):
        conn.execute("ALTER TABLE assignments ADD COLUMN start_selfie_url TEXT")
    if "end_photo_url" not in _columns(conn, "assignments"):
        conn.execute("ALTER TABLE assignments ADD COLUMN end_photo_url TEXT")
    if "started_at" not in _columns(conn, "assignments"):
        conn.execute("ALTER TABLE assignments ADD COLUMN started_at TEXT")


# The member cooperative this tenant owns a row. Defaults to the original
# cooperative (id = 1), which is backfilled below for old databases.
_TENANT_TABLES = {
    "cooperative_federations",  # master table (created here)
    "users",
    "workers",
    "bookings",
    "assignments",
    "declines",
    "sessions",
    "disputes",
    "settlements",
    "feedback",
}


def _migration_5_federation_tenants(conn: sqlite3.Connection) -> None:
    """Generalize the singleton `cooperative` table into a multi-row federation
    and thread `cooperative_id` through every tenant table.

    - Creates `cooperative_federations` (the new profile table).
    - Copies any legacy `cooperative` row into it (so Bhopal's profile survives).
    - Seeds the default row id=1 if nothing did.
    - Adds `cooperative_id` columns (default 1) to every tenant table, guarding
      with PRAGMA checks so a fresh database (already fully defined by SCHEMA)
      is left untouched.
    """
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    if "cooperative_federations" not in tables:
        conn.execute(
            """
            CREATE TABLE cooperative_federations (
                id                INTEGER PRIMARY KEY,
                name              TEXT    NOT NULL,
                code              TEXT    NOT NULL UNIQUE,
                region            TEXT,
                short_name        TEXT    NOT NULL,
                registration_id   TEXT,
                established       INTEGER,
                area              TEXT,
                radius_km         REAL,
                verified          INTEGER NOT NULL DEFAULT 0,
                worker_kyc        INTEGER NOT NULL DEFAULT 0,
                payments_verified INTEGER NOT NULL DEFAULT 0,
                secretary         TEXT,
                coordinator       TEXT,
                last_meeting      TEXT,
                weekly_job_limit  INTEGER NOT NULL DEFAULT 6 CHECK (weekly_job_limit > 0),
                fund_allocation   TEXT    NOT NULL DEFAULT '{}',
                created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    # Copy legacy profile into the federation, if the old table exists.
    if "cooperative" in tables and conn.execute("SELECT COUNT(*) FROM cooperative_federations").fetchone()[0] == 0:
        copied = conn.execute(
            """
            INSERT INTO cooperative_federations
                (id, name, short_name, registration_id, established, area, radius_km,
                 verified, worker_kyc, payments_verified, secretary, coordinator,
                 last_meeting, weekly_job_limit, fund_allocation)
            SELECT id, name, short_name, registration_id, established, area, radius_km,
                   verified, worker_kyc, payments_verified, secretary, coordinator,
                   last_meeting, weekly_job_limit, fund_allocation
            FROM cooperative
            """
        ).rowcount
        log.info("backfilled %d cooperative row(s) into cooperative_federations", copied)

    # Ensure the default cooperative (id = 1) always exists.
    if conn.execute("SELECT COUNT(*) FROM cooperative_federations WHERE id = 1").fetchone()[0] == 0:
        from app.cooperative import DEFAULTS
        cols = ", ".join(DEFAULTS)
        marks = ", ".join("?" for _ in DEFAULTS)
        conn.execute(
            f"INSERT INTO cooperative_federations (id, code, {cols}) VALUES (1, ?, {marks})",
            ("SABHA-2026", *DEFAULTS.values()),
        )

    _DEFAULT_CODE = os.environ.get("SAHAKARSETU_COOPERATIVE_CODE", "SABHA-2026").strip().upper() or "SABHA-2026"
    # Make the default cooperative carry the configured code if it was inserted above.
    conn.execute("UPDATE cooperative_federations SET code = ? WHERE code IS NULL OR code = '' ", (_DEFAULT_CODE,))

    # Add cooperative_id columns to tenant tables that lack them. SQLite cannot
    # add a REFERENCES column with a non-NULL default, so the FK is omitted on
    # legacy databases (referential integrity is still enforced for new writes
    # via the application tenant scope).
    for table in ("users", "workers", "bookings", "assignments", "declines", "sessions",
                  "disputes", "settlements", "feedback", "standard_rates"):
        if table in tables and "cooperative_id" not in _columns(conn, table):
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN cooperative_id INTEGER NOT NULL DEFAULT 1"
            )
    # Tenant indexes; safe to create (columns now exist on every table above).
    conn.execute("CREATE INDEX IF NOT EXISTS idx_workers_cooperative ON workers (cooperative_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_cooperative ON bookings (cooperative_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_assignments_cooperative ON assignments (cooperative_id)")


def _migration_6_provider_profile_tables(conn: sqlite3.Connection) -> None:
    """Phase B: skills, certificates, portfolio, worker documents.

    Additive only — every table is created with IF NOT EXISTS and guarded by
    PRAGMA checks so a fresh database (columns already in SCHEMA) is untouched.
    """
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_skills (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id       INTEGER NOT NULL REFERENCES workers(id),
            skill           TEXT    NOT NULL,
            level           TEXT    NOT NULL DEFAULT 'intermediate'
                            CHECK (level IN ('beginner', 'intermediate', 'expert')),
            verified        INTEGER NOT NULL DEFAULT 0,
            verified_by     INTEGER REFERENCES users(id),
            verified_at     TEXT,
            cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (worker_id, skill)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS certifications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id       INTEGER NOT NULL REFERENCES workers(id),
            name            TEXT    NOT NULL,
            issuing_org     TEXT,
            issue_date      TEXT,
            expiry_date     TEXT,
            document        TEXT,
            verified        INTEGER NOT NULL DEFAULT 0,
            verified_by     INTEGER REFERENCES users(id),
            verified_at     TEXT,
            cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (worker_id, name, issuing_org, issue_date)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id       INTEGER NOT NULL REFERENCES workers(id),
            image_url       TEXT    NOT NULL,
            caption         TEXT,
            category        TEXT,
            verified        INTEGER NOT NULL DEFAULT 0,
            verified_by     INTEGER REFERENCES users(id),
            verified_at     TEXT,
            cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
            created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id       INTEGER NOT NULL REFERENCES workers(id),
            document_type   TEXT    NOT NULL,
            file_url        TEXT    NOT NULL,
            uploaded_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            cooperative_id  INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
            UNIQUE (worker_id, document_type, file_url)
        )
        """
    )
    if "worker_skills" not in tables:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_worker_skills_worker ON worker_skills (worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_worker_skills_coop ON worker_skills (cooperative_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_certifications_worker ON certifications (worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_certifications_coop ON certifications (cooperative_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_certifications_verified ON certifications (verified)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_worker ON portfolio_items (worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_coop ON portfolio_items (cooperative_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_worker_documents_worker ON worker_documents (worker_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_worker_documents_coop ON worker_documents (cooperative_id)")


def _migration_7_welfare_benefits_and_grievances(conn: sqlite3.Connection) -> None:
    """Phase E: benefits, insurance policies, and worker grievances."""
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    statements = [
        """
        CREATE TABLE IF NOT EXISTS benefits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id),
            kind TEXT NOT NULL CHECK (kind IN ('pension', 'medical', 'disability', 'other')),
            name TEXT NOT NULL, description TEXT,
            eligible INTEGER NOT NULL DEFAULT 0,
            claimed INTEGER NOT NULL DEFAULT 0,
            amount_rupees REAL CHECK (amount_rupees IS NULL OR amount_rupees >= 0),
            start_date TEXT, end_date TEXT, document TEXT,
            cooperative_id INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS insurance_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('health', 'accident', 'life', 'liability', 'other')),
            insurer TEXT, policy_number TEXT,
            premium_rupees REAL NOT NULL CHECK (premium_rupees >= 0),
            premium_paid INTEGER NOT NULL DEFAULT 0,
            coverage_paise INTEGER NOT NULL CHECK (coverage_paise >= 0),
            start_date TEXT, end_date TEXT, active INTEGER NOT NULL DEFAULT 1,
            cooperative_id INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS grievances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER REFERENCES workers(id),
            raised_by_user_id INTEGER REFERENCES users(id),
            kind TEXT NOT NULL CHECK (kind IN ('wage', 'safety', 'equipment', 'assignment', 'other')),
            title TEXT NOT NULL, description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'triaged', 'in_progress', 'resolved', 'rejected')),
            resolution TEXT, priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
            cooperative_id INTEGER NOT NULL DEFAULT 1 REFERENCES cooperative_federations(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_benefits_worker ON benefits (worker_id)",
        "CREATE INDEX IF NOT EXISTS idx_benefits_coop ON benefits (cooperative_id)",
        "CREATE INDEX IF NOT EXISTS idx_insurance_coop ON insurance_policies (cooperative_id)",
        "CREATE INDEX IF NOT EXISTS idx_insurance_active ON insurance_policies (active)",
        "CREATE INDEX IF NOT EXISTS idx_grievances_worker ON grievances (worker_id)",
        "CREATE INDEX IF NOT EXISTS idx_grievances_status ON grievances (status)",
        "CREATE INDEX IF NOT EXISTS idx_grievances_coop ON grievances (cooperative_id)",
    ]
    for stmt in statements:
        conn.execute(stmt)


MIGRATIONS = (
    (1, _migration_1_customer_owner),
    (2, _migration_2_integrity_triggers),
    (3, _migration_3_worker_status_and_replies),
    (4, _migration_4_urgency_and_proof_of_work),
    (5, _migration_5_federation_tenants),
    (6, _migration_6_provider_profile_tables),
    (7, _migration_7_welfare_benefits_and_grievances),
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


def get_database_engine_info() -> dict[str, str]:
    """Returns metadata about active database engine and storage driver."""
    if DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")):
        return {
            "engine": "PostgreSQL",
            "provider": "Cloud Managed (Neon.tech / Supabase)",
            "concurrency": "Multi-client row-level locking",
        }
    return {
        "engine": "SQLite",
        "provider": "Local Embedded WAL Mode",
        "path": str(DB_PATH),
        "concurrency": "Write-Ahead Logging (WAL)",
    }
