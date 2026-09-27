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


# ── the deployed configuration: a Postgres URL in front of a SQLite file ────
#
# Render's Docker image pins SAHAKARSETU_DB=/data/sahakarsetu.db and the service
# also has a Neon DATABASE_URL set. get_connection() always returns SQLite, so
# use_postgres() reports True while every statement still runs against SQLite.
# Migrations that branch on use_postgres() therefore issued Postgres-only DDL
# (ALTER TABLE ... DROP CONSTRAINT) against SQLite, which is a syntax error there
# and killed the service in its lifespan -- "Application startup failed. Exiting."

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
