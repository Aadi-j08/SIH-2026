"""
Tests for Dual-Database Engine Configuration and Schema Integrity.
"""
import sqlite3

import pytest

from app import database
from app.database import get_database_engine_info, connection, migrate


def test_database_engine_info():
    info = get_database_engine_info()
    assert "engine" in info
    assert info["engine"] in ("SQLite", "PostgreSQL")
    assert "concurrency" in info


# ── the configuration that broke production ─────────────────────────────────
#
# Render's Docker image pins SAHAKARSETU_DB=/data/sahakarsetu.db and the service
# also has a Neon DATABASE_URL set. get_connection() used to ignore the URL and
# always return SQLite, so use_postgres() reported True while every statement ran
# against a file in the container's ephemeral disk -- every worker and council
# account created after a redeploy vanished. Migrations that branched on
# use_postgres() also issued Postgres-only DDL (ALTER TABLE ... DROP CONSTRAINT)
# against SQLite, a syntax error there, killing the service in its lifespan:
# "Application startup failed. Exiting."
#
# get_connection() now honours DATABASE_URL. These tests pin the fix: the URL
# decides the connection, and migrate() stays on SQLite regardless because it
# is only ever handed a real SQLite connection.

LEGACY_WORKERS = """
CREATE TABLE workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    trade TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    jobs_this_week INTEGER NOT NULL DEFAULT 0 CHECK (jobs_this_week >= 0),
    rating REAL,
    availability TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active')),
    cooperative_id INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    base_rating REAL,
    rating_count INTEGER NOT NULL DEFAULT 0
)
"""


def _legacy_db(path):
    """A database as it looked just before migration 10, at version 9."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(LEGACY_WORKERS)
    conn.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT)"
    )
    for version in range(1, 10):
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
    conn.execute(
        "INSERT INTO workers (id, name, phone, trade, latitude, longitude) "
        "VALUES (1, 'Meena', '9000000001', 'plumbing', 23.2, 77.4)"
    )
    conn.commit()
    return conn


def test_migrations_use_the_connection_not_the_configured_url(tmp_path, monkeypatch):
    """A Postgres DATABASE_URL must not push migrations down the Postgres path."""
    path = tmp_path / "render_like.db"
    conn = _legacy_db(path)
    try:
        monkeypatch.setattr(
            database, "DATABASE_URL", "postgresql://user:pw@ep-cool.us-east-2.aws.neon.tech/db"
        )
        assert database.use_postgres() is True, "this is the trap: the URL says Postgres"
        assert isinstance(conn, sqlite3.Connection), "but the connection is SQLite"

        applied = migrate(conn)

        assert 10 in applied
        ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='workers'").fetchone()["sql"]
        assert "CHECK (status IN ('pending', 'active', 'rejected'))" in ddl
    finally:
        conn.close()


def test_migration_10_preserves_rows_indexes_and_triggers_under_a_postgres_url(tmp_path, monkeypatch):
    """The SQLite rebuild must survive the URL that misleads use_postgres()."""
    monkeypatch.setattr(
        database, "DATABASE_URL", "postgresql://user:pw@ep-cool.us-east-2.aws.neon.tech/db"
    )
    path = tmp_path / "render_like.db"
    conn = _legacy_db(path)
    try:
        conn.execute("CREATE INDEX idx_workers_trade ON workers (trade)")
        for event in ("insert", "update"):
            conn.execute(
                f"CREATE TRIGGER trg_workers_rating_{event} BEFORE {event.upper()} ON workers "
                "WHEN NEW.rating IS NOT NULL AND (NEW.rating < 1 OR NEW.rating > 5) "
                "BEGIN SELECT RAISE(ABORT, 'rating must be 1 to 5'); END"
            )
        conn.commit()

        migrate(conn)

        assert conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE tbl_name='workers' AND type='index'")}
        assert "idx_workers_trade" in names
        triggers = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE tbl_name='workers' AND type='trigger'")}
        assert "trg_workers_rating_insert" in triggers

        # the point of the migration, and the reason the service was down
        conn.execute("UPDATE workers SET status='rejected' WHERE id=1")
        assert conn.execute("SELECT status FROM workers WHERE id=1").fetchone()[0] == "rejected"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE workers SET status='bogus' WHERE id=1")
    finally:
        conn.close()


def test_core_tables_and_indexes_exist(db_path):
    with connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "workers" in tables
        assert "bookings" in tables
        assert "assignments" in tables
        assert "users" in tables
        assert "disputes" in tables
        assert "settlements" in tables
        assert "cooperative_federations" in tables
        cols = {row[1] for row in conn.execute("PRAGMA table_info(cooperative_federations)")}
        for c in ("id", "name", "code", "region", "short_name", "weekly_job_limit", "fund_allocation"):
            assert c in cols
        for t in ("workers", "bookings", "users", "assignments", "disputes", "settlements"):
            tenant_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({t})")}
            assert "cooperative_id" in tenant_cols, f"{t} missing cooperative_id"


# ── the fix: the URL decides the connection ─────────────────────────────────

NEON = "postgresql://user:pw@ep-cool.us-east-2.aws.neon.tech/db"


def test_get_connection_honours_the_postgres_url(tmp_path, monkeypatch):
    """A Postgres URL must produce the psycopg connection, not a local file.

    This is the assertion that failed in production: a new worker registered,
    the row went into the container's ephemeral disk, and it was gone after the
    next deploy. app.pg.get_connection is stubbed so no server is needed -- what
    is under test is the branch, not the driver.
    """
    import app.pg

    sentinel = object()
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "should-not-be-used.db")
    monkeypatch.setattr(database, "DATABASE_URL", NEON)
    monkeypatch.setattr(app.pg, "get_connection", lambda: sentinel)

    assert database.get_connection() is sentinel
    assert not (tmp_path / "should-not-be-used.db").exists(), "wrote to the local file"


def test_active_engine_agrees_with_the_url(monkeypatch):
    """active_engine() used to hardcode "sqlite", so it could not disagree loudly."""
    monkeypatch.setattr(database, "DATABASE_URL", NEON)
    assert database.active_engine() == "postgresql"
    assert database.use_postgres() is True

    monkeypatch.setattr(database, "DATABASE_URL", None)
    assert database.active_engine() == "sqlite"


def test_engine_info_reflects_the_chosen_engine(monkeypatch):
    monkeypatch.setattr(database, "DATABASE_URL", NEON)
    info = get_database_engine_info()
    assert info["engine"] == "PostgreSQL"
    assert "path" not in info, "must not advertise a local file it is not using"


def test_unparseable_database_url_fails_loudly(tmp_path, monkeypatch):
    """A typo'd DATABASE_URL must not silently resolve to the ephemeral disk.

    This is the original outage wearing a different hat: the URL is present but
    unusable, so use_postgres() is False and the old code quietly used SQLite.
    """
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "sahakarsetu.db")
    monkeypatch.setattr(database, "DATABASE_URL", "mysql://user:pw@host/db")

    with pytest.raises(RuntimeError, match="not a PostgreSQL URL"):
        database.get_connection()


def test_blank_database_url_is_not_treated_as_misconfiguration(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "sahakarsetu.db")
    monkeypatch.setattr(database, "DATABASE_URL", "   ")
    assert isinstance(database.get_connection(), sqlite3.Connection)


def test_booking_flow_does_not_bypass_the_engine(tmp_path, monkeypatch):
    """open_connection() had its own sqlite3.connect, a second route to the file."""
    import app.booking_flow_db as booking_flow_db

    sentinel = object()
    monkeypatch.setattr(database, "DATABASE_URL", NEON)
    monkeypatch.setattr(database, "get_connection", lambda: sentinel)

    assert booking_flow_db.open_connection() is sentinel


def test_booking_flow_still_uses_sqlite_without_a_url(db_path):
    import app.booking_flow_db as booking_flow_db

    assert isinstance(booking_flow_db.open_connection(), sqlite3.Connection)


# ── schema.sql must cover what the SQLite path creates ───────────────────────
#
# Postgres never runs migrate(); init_db() applies schema.sql instead. Any table
# or column the SQLite path adds but schema.sql omits simply does not exist in
# production. Two such gaps shipped unnoticed: payment_ledger and
# booking_ratings (created lazily by booking_flow_db) and the worker_documents
# verification and blob columns. This walks both paths and compares them.
#
# The SQLite side is not just SCHEMA + migrations. init_db() runs the migration
# chain and stops, so a *fresh* database also lacks the columns the booking flow
# adds later, on its first request, with ALTER TABLE ADD COLUMN
# (app/booking_flow_db.py:_pending_changes). Comparing only the migration chain
# therefore compares two databases that are both missing those columns and
# passes -- which is exactly how assignments.score_breakdown, .explanation,
# .allocation_score, bookings.completed_at and workers.base_rating / .rating_count
# reached a half-built Postgres schema. The helpers below run the full SQLite
# path, guard included.

def _sqlite_columns_after_boot(db_path):
    """Every table and column the SQLite path ends up with once a request has run.

    init_db() has already been applied by the db_path fixture, so this only adds
    the booking flow's own schema guard -- the same thing
    booking_flow_connection() does on its first request.
    """
    import app.booking_flow_db as booking_flow_db

    conn = booking_flow_db.open_connection()
    try:
        booking_flow_db.ensure_booking_flow_schema(conn)
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return {
            # sqlite_sequence is SQLite's internal AUTOINCREMENT bookkeeping,
            # not a table the app defines.
            table: {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for table in tables
            if not table.startswith("sqlite_")
        }
    finally:
        conn.close()


def _declarations_from_schema_sql():
    """Every table and column schema.sql declares, with its declaration text.

    Parsed without a server, and keyed by declaration rather than by column name
    alone so a test can pin the type and default too.
    """
    import re

    text = (database.BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    parsed = {}
    for match in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\((.*?)\n\);", text, re.S):
        table, body = match.group(1), match.group(2)
        declarations = {}
        for line in body.split("\n"):
            line = line.split("--")[0].strip().rstrip(",")
            if not line:
                continue
            first = line.split()[0].upper()
            if first in {"UNIQUE", "CHECK", "FOREIGN", "PRIMARY", "CONSTRAINT"}:
                continue
            declarations[line.split()[0]] = " ".join(line.split())
        parsed[table] = declarations
    return parsed


def _columns_from_schema_sql():
    """Every table and column schema.sql declares, parsed without a server."""
    return {
        table: set(declarations)
        for table, declarations in _declarations_from_schema_sql().items()
    }


def test_schema_sql_is_not_missing_anything_the_migrations_create(db_path):
    """Postgres gets schema.sql; SQLite gets the migration chain plus the booking
    flow's guard. They must agree on every table and column."""
    migrated = _sqlite_columns_after_boot(db_path)
    declared = _columns_from_schema_sql()

    missing_tables = sorted(set(migrated) - set(declared))
    assert missing_tables == [], f"schema.sql is missing tables: {missing_tables}"

    missing_columns = {
        table: sorted(migrated[table] - declared.get(table, set()))
        for table in migrated
        if migrated[table] - declared.get(table, set())
    }
    assert missing_columns == {}, f"schema.sql is missing columns: {missing_columns}"


# The booking flow adds its columns with ALTER TABLE on a database that lacks
# them, so on Postgres -- where schema.sql is the only thing that runs at boot --
# anything it would ALTER has to be declared in schema.sql instead. This asks
# _pending_changes what it would do to a database that has none of them and holds
# schema.sql to every answer.
#
# It has to be a legacy-shaped database rather than the fresh one: the guard only
# adds assignments.allocation_score when no ASSIGNMENT_SCORE_COLUMNS member
# exists, and SCHEMA declares assignments.score, so a fresh database never gets
# that ALTER and a test built on a fresh database cannot catch it going missing.
LEGACY_BOOKING_FLOW_DB = """
CREATE TABLE workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    jobs_this_week INTEGER NOT NULL DEFAULT 0,
    rating REAL
);
CREATE TABLE bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE TABLE assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    worker_id INTEGER NOT NULL
);
"""

# The SQLite declaration is the source of truth; the Postgres one is what
# schema.sql must say instead. completed_at is TEXT on SQLite because that is
# how SQLite spells a timestamp -- schema.sql declares every other *_at column
# as TIMESTAMP WITH TIME ZONE, and so must this one.
BOOKING_FLOW_COLUMNS = {
    ("assignments", "allocation_score"): ("REAL", "REAL"),
    ("assignments", "score_breakdown"): ("TEXT", "TEXT"),
    ("assignments", "explanation"): ("TEXT", "TEXT"),
    ("bookings", "completed_at"): ("TEXT", "TIMESTAMP WITH TIME ZONE"),
    ("workers", "base_rating"): ("REAL", "REAL"),
    ("workers", "rating_count"): ("INTEGER NOT NULL DEFAULT 0", "INTEGER NOT NULL DEFAULT 0"),
}


def _columns_the_booking_flow_would_add(path):
    """The columns _pending_changes ALTERs into a database that has none of them.

    Returns {(table, column): declaration} using booking_flow_db's own DDL, so
    this stays right if those declarations ever change.
    """
    import re

    import app.booking_flow_db as booking_flow_db

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(LEGACY_BOOKING_FLOW_DB)
        added = {}
        for statement in booking_flow_db._pending_changes(conn):
            match = re.match(r"ALTER TABLE (\w+) ADD COLUMN (\w+)\s+(.*)", statement)
            if match:
                added[(match.group(1), match.group(2))] = " ".join(match.group(3).split())
        return added
    finally:
        conn.close()


def test_booking_flow_alter_table_columns_are_all_declared_in_schema_sql(tmp_path):
    """A Postgres boot must not depend on the booking flow fixing the schema."""
    added = _columns_the_booking_flow_would_add(tmp_path / "legacy.db")
    declared = _columns_from_schema_sql()

    assert set(added) == set(BOOKING_FLOW_COLUMNS), (
        "the booking flow's ADD COLUMN set changed; update BOOKING_FLOW_COLUMNS "
        f"and schema.sql. Now: {sorted(added)}"
    )
    missing = {
        f"{table}.{column}": declaration
        for (table, column), declaration in added.items()
        if column not in declared.get(table, set())
    }
    assert missing == {}, (
        "schema.sql is missing columns that app/booking_flow_db.py only adds with "
        f"ALTER TABLE on the first request: {missing}"
    )


def test_schema_sql_types_the_booking_flow_columns_like_sqlite_does(tmp_path):
    """The column has to exist *and* mean the same thing once it is there."""
    added = _columns_the_booking_flow_would_add(tmp_path / "legacy.db")
    declarations = _declarations_from_schema_sql()

    for (table, column), (sqlite_decl, postgres_decl) in BOOKING_FLOW_COLUMNS.items():
        assert added[(table, column)] == sqlite_decl, (
            f"{table}.{column}: booking_flow_db declares {added[(table, column)]!r}, "
            f"this test expects {sqlite_decl!r}"
        )
        actual = declarations.get(table, {}).get(column)
        assert actual == f"{column} {postgres_decl}", (
            f"schema.sql declares {table}.{column} as {actual!r}; expected "
            f"{column + ' ' + postgres_decl!r}"
        )


def test_schema_sql_declares_the_booking_flow_tables():
    """booking_flow_db creates these lazily on SQLite; Postgres has no such path."""
    declared = _columns_from_schema_sql()
    assert "payment_ledger" in declared, "payment_ledger missing from schema.sql"
    assert "booking_ratings" in declared, "booking_ratings missing from schema.sql"
    assert {"id", "booking_id", "party", "amount_paise"} <= declared["payment_ledger"]
    assert {"booking_id", "worker_id", "rating"} <= declared["booking_ratings"]


def test_schema_sql_declares_the_document_blob_and_verification_columns():
    """Documents must survive a redeploy: the bytes live in the database."""
    declared = _columns_from_schema_sql()
    assert "worker_documents" in declared
    for column in ("filename", "content_type", "byte_size", "content"):
        assert column in declared["worker_documents"], f"worker_documents.{column} missing"
    for column in ("verified", "verified_by", "verified_at", "rejection_reason"):
        assert column in declared["worker_documents"], f"worker_documents.{column} missing"


# ── the boot path must be runnable on PostgreSQL ─────────────────────────────
#
# The first cut of this branch executed the SCHEMA constant against PostgreSQL.
# SCHEMA is SQLite dialect (`INTEGER PRIMARY KEY AUTOINCREMENT`), so the very
# first statement was a syntax error and the service died in its lifespan --
# the same outage this branch fixes. These assert the boot path is portable.

def test_schema_sql_is_a_superset_of_the_schema_constant():
    """Dropping SCHEMA from the Postgres path is only safe if schema.sql covers it."""
    import re

    def parse(text):
        found = {}
        for match in re.finditer(
            r"CREATE TABLE(?: IF NOT EXISTS)? (\w+)\s*\((.*?)\n\)\s*;", text, re.S
        ):
            table, body = match.group(1), match.group(2)
            columns = set()
            for line in body.split("\n"):
                line = line.split("--")[0].strip().rstrip(",")
                if not line:
                    continue
                if line.split()[0].upper() in {
                    "UNIQUE", "CHECK", "FOREIGN", "PRIMARY", "CONSTRAINT"
                }:
                    continue
                columns.add(line.split()[0])
            found[table] = columns
        return found

    constant = parse(database.SCHEMA)
    declared = parse((database.BASE_DIR / "schema.sql").read_text(encoding="utf-8"))

    assert not set(constant) - set(declared), "schema.sql is missing a SCHEMA table"
    for table, columns in constant.items():
        missing = columns - declared[table]
        assert not missing, f"schema.sql {table} is missing {sorted(missing)}"


def test_postgres_boot_applies_schema_sql_and_not_the_schema_constant(monkeypatch):
    """SCHEMA must not be executed against PostgreSQL, and the assert must run."""
    import app.pg

    calls = []
    monkeypatch.setattr(database, "DATABASE_URL", NEON)
    monkeypatch.setattr(app.pg, "get_connection", lambda: object())
    monkeypatch.setattr(
        database, "connection",
        lambda: _RecordingConnection(calls),
    )
    monkeypatch.setattr(database, "_assert_postgres_schema", lambda: calls.append("asserted"))

    database.init_db()

    # _upgrade_postgres_columns issues single ALTERs; the script is the only
    # multi-statement payload, and it must be schema.sql and not SCHEMA.
    scripts = [c for c in calls if "CREATE TABLE" in c]
    assert len(scripts) == 1, f"expected one DDL script, got {len(scripts)}"
    # Strip comments first: schema.sql mentions AUTOINCREMENT while explaining
    # why assistant_audit is declared there rather than in assistant.py.
    ddl = "\n".join(
        line.split("--")[0] for line in scripts[0].splitlines()
    )
    assert "AUTOINCREMENT" not in ddl, (
        "the SQLite SCHEMA constant was executed against PostgreSQL"
    )
    assert "CREATE TABLE IF NOT EXISTS workers" in scripts[0]
    assert "assistant_audit" in scripts[0]

    # Existing databases need ALTERs, because CREATE TABLE IF NOT EXISTS skips
    # a table that already exists in an older shape. Counted against the tuple
    # rather than a literal so the set can grow without a silent skip.
    alters = [c for c in calls if c.startswith("ALTER TABLE")]
    assert len(alters) == len(database._POSTGRES_COLUMN_UPGRADES), (
        f"expected one ALTER per _POSTGRES_COLUMN_UPGRADES entry "
        f"({len(database._POSTGRES_COLUMN_UPGRADES)}), got {len(alters)}"
    )
    assert all("IF NOT EXISTS" in a for a in alters)
    # The eight document columns are what motivated the mechanism; they stay
    # covered whatever else is added alongside them.
    document_alters = [a for a in alters if a.startswith("ALTER TABLE worker_documents")]
    assert len(document_alters) == 8, (
        f"expected the 8 document columns, got {len(document_alters)}"
    )

    assert "asserted" in calls, "schema shape was never verified"


class _RecordingConnection:
    """Stands in for a Postgres connection and records executescript calls."""

    def __init__(self, calls):
        self._calls = calls
        self.row_factory = None
        self.autocommit = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def executescript(self, script):
        self._calls.append(script)

    def execute(self, sql, params=()):
        self._calls.append(sql)
        return self

    def fetchone(self):
        # _upgrade_postgres_columns asks information_schema.tables whether each
        # table exists yet; report yes so the ALTER path is exercised.
        return (1,)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def test_postgres_upgrade_covers_the_document_blob_columns():
    """CREATE TABLE IF NOT EXISTS cannot add columns to an existing table."""
    from app import pg

    # The AUTOINCREMENT rewrite exists for exactly this lazy DDL.
    assert "SERIAL PRIMARY KEY" in pg._translate(
        "CREATE TABLE IF NOT EXISTS assistant_audit ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL)",
        has_params=False,
    )


# ── the fail-loud guard must cover the booking flow too ──────────────────────

def test_booking_flow_shares_the_fail_loud_guard(tmp_path, monkeypatch):
    """open_connection() used to call sqlite3.connect directly, bypassing the guard.

    The booking flow is the highest-value write path, so leaving it able to
    reach the ephemeral disk under a misconfigured DATABASE_URL would preserve
    the original outage.
    """
    import app.booking_flow_db as booking_flow_db

    monkeypatch.setattr(database, "DATABASE_URL", "mysql://user:pw@host/db")
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "sahakarsetu.db")

    with pytest.raises(RuntimeError, match="not a PostgreSQL URL"):
        booking_flow_db.open_connection()

    assert not (tmp_path / "sahakarsetu.db").exists(), "opened the ephemeral file"


def test_booking_flow_postgres_connection_is_not_sqlite_tuned(tmp_path, monkeypatch):
    """The SQLite PRAGMA tuning must be skipped for the psycopg wrapper."""
    import app.booking_flow_db as booking_flow_db
    import app.pg

    sentinel = object()
    monkeypatch.setattr(database, "DATABASE_URL", NEON)
    monkeypatch.setattr(app.pg, "get_connection", lambda: sentinel)

    assert booking_flow_db.open_connection() is sentinel


# ── document blobs must not be streamed by listings ──────────────────────────

def test_document_queries_select_has_content_not_the_bytes():
    """`SELECT *` plus a BYTEA column would pull every ID scan over the wire."""
    import inspect

    import app.profile as profile

    source = inspect.getsource(profile)
    assert "SELECT * FROM worker_documents" not in source, (
        "profile.py selects document rows with SELECT *, which now includes the "
        "content blob; use the _DOCUMENT_COLUMNS projection instead"
    )
    assert "content IS NOT NULL AS has_content" in source

    from app.routers import workers

    assert "SELECT * FROM worker_documents" not in inspect.getsource(workers)


def test_document_content_endpoint_still_reads_the_blob():
    """The one query that genuinely needs the bytes must still fetch them."""
    import inspect

    import app.profile as profile

    assert "SELECT content, content_type, filename FROM worker_documents" in inspect.getsource(
        profile
    )
