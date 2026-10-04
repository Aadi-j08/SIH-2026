"""
Integration suite for the PostgreSQL path in app/pg.py, against a real server.

Everything else in tests/ runs on SQLite. That is why the defects this suite
covers survived a full green suite: three of them live on paths only Postgres
reaches (`database.connection()` atomicity, `cursor.lastrowid`, `BEGIN
IMMEDIATE`), and the rest are places where SQLite's TEXT timestamps are assumed
to be strings.

tests/test_pg_connection.py and tests/test_pg_translate.py cover the first group
against a *fake* driver -- they assert the SQL that is sent, not that PostgreSQL
accepts it, returns sane values, or enforces what was asked of it. This file
closes that gap by executing every one of those paths against a live server.

It also does the one schema check the text-parsing drift test cannot do: it builds
the SQLite schema with the real `database.init_db()` (plus the two tables the app
creates lazily on first use) and compares the resulting table and column names
against what the Postgres boot actually created, queried from
`information_schema`. Parsing `schema.sql` as text cannot catch a table that only
exists in one of the two dialects.

RUN IT
------
By default this file SKIPS. Set POSTGRES_TEST_URL to a server you are willing to
have databases created on and dropped from:

    POSTGRES_TEST_URL=postgresql://user@localhost:5432/postgres \
        python3 -m pytest tests/test_postgres_integration.py -q

`DATABASE_URL` is deliberately NOT consulted for the skip decision. It is what
app/database.py branches on, so reading it here would either silently point this
suite at whatever the developer's shell exports, or (once monkeypatched below)
leak a Postgres URL into the SQLite tests that share the run.

Each run gets its own randomly named throwaway database, created on the server
given by POSTGRES_TEST_URL and dropped again when the session ends. Nothing here
ever touches a database named by the operator.

The application code is exercised unmodified: `app.database.DATABASE_URL` is
monkeypatched to the throwaway database, and every test then calls the real
`init_db()`, `connection()`, `booking_flow_db.open_connection()` and
`immediate_transaction()`. Nothing the suite needs is reimplemented here.

No test-only shims
------------------
An earlier version of this file had to carry one. app/pg.py installed
`_row_factory(cursor, values)` as `raw.row_factory`, which is psycopg **2**'s
two-argument convention; psycopg 3 calls a row_factory with one argument -- the
cursor -- and expects a row maker back (psycopg/cursor.py `_make_row_maker`). So
the first statement on any Postgres connection, the `BEGIN` app/pg.py issues
first, raised

    TypeError: _row_factory() missing 1 required positional argument: 'values'

and init_db() died on boot before schema.sql was sent: the Postgres path had
never executed a single statement, which is why the fake-driver tests in
test_pg_connection.py all passed. The adapter here (`_psycopg3_row_factory`) let
sections A-H be measured anyway, and is gone now that app/pg.py's factory matches
what psycopg 3.3.6 actually calls.

Remaining `test_known_defect_` tests are asserted as they currently behave, each
with a comment saying so, so a real run reports what is still broken instead of
hiding it. See TIMESTAMP_MIGRATION_REPORT.md.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import sqlite3
import threading
import uuid
from urllib.parse import urlsplit, urlunsplit

import pytest

from app import auth, booking_flow_db, database, pg


# ── skip guard ───────────────────────────────────────────────────────────────
#
# Read at import time from POSTGRES_TEST_URL only. See the module docstring for
# why DATABASE_URL is not a fallback here.

TEST_SERVER_URL = os.environ.get("POSTGRES_TEST_URL", "").strip()

# The maintenance connection is separate because CREATE/DROP DATABASE cannot run
# through Neon's pooled endpoint (pgbouncer in transaction mode rejects them).
# So POSTGRES_TEST_URL may be the *pooled* URL -- which is the point, since
# pgbouncer is what production uses and what this suite exists to verify -- while
# the admin connection stays on the unpooled URL.
TEST_ADMIN_URL = os.environ.get("POSTGRES_TEST_ADMIN_URL", "").strip() or TEST_SERVER_URL

try:  # psycopg ships with the app, but do not fail collection without it.
    import psycopg
except ImportError:  # pragma: no cover - environment problem, not a test result
    psycopg = None  # type: ignore[assignment]

SKIP_REASON = (
    "POSTGRES_TEST_URL is not set. This suite needs a real PostgreSQL server; "
    "point POSTGRES_TEST_URL at one to run it (see the module docstring)."
)

pytestmark = [
    pytest.mark.skipif(not TEST_SERVER_URL, reason=SKIP_REASON),
    pytest.mark.skipif(psycopg is None, reason="psycopg is not installed"),
]


def _admin_connect():
    """A plain psycopg connection to the maintenance database, autocommit.

    Used only to CREATE/DROP the throwaway database and to open the *second*
    connection in the lock test. The application is never reached this way, so
    nothing here can hide a defect in app/pg.py.
    """
    return psycopg.connect(TEST_ADMIN_URL, autocommit=True, prepare_threshold=None)


def _database_url_for(name: str) -> str:
    """The maintenance URL with its database replaced by `name`.

    Parsed rather than regex-substituted. Neon URLs carry a query string
    (`?sslmode=require&channel_binding=require`), and the earlier regex stripped
    the database name but appended the new one *after* the query, yielding
    `.../?sslmode=requiresahakarsetu_it_...` and
    `invalid sslmode value`. A local server with no query string never showed it.
    """
    parts = urlsplit(TEST_ADMIN_URL)
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{name}", parts.query, parts.fragment)
    )


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def pg_database() -> str:
    """A freshly created, empty database, booted by the real init_db(); dropped
    when the session ends.

    Only app.database.DATABASE_URL is patched. app/pg.py reads the URL through
    that module at call time, so one assignment is enough -- when it held its own
    copy taken at import time it had to be repointed separately, and a test that
    patched only app.database silently kept talking to the old database.

    The DATABASE_URL patch is applied inside this fixture (a hand-rolled
    MonkeyPatch, because the `monkeypatch` fixture is function-scoped) so it
    cannot leak into the SQLite tests that share the session.
    """
    name = f"sahakarsetu_it_{uuid.uuid4().hex[:12]}"
    with _admin_connect() as admin:
        admin.execute(f'CREATE DATABASE "{name}"')

    url = _database_url_for(name)

    def _drop() -> None:
        with _admin_connect() as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (name,),
            )
            admin.execute(f'DROP DATABASE IF EXISTS "{name}"')

    patch = pytest.MonkeyPatch()
    try:
        patch.setattr(database, "DATABASE_URL", url)
        pg._reset_thread_connection()
        database.init_db()
    except BaseException:
        # A failed boot must not leave a database behind on the server.
        pg._reset_thread_connection()
        patch.undo()
        _drop()
        raise

    try:
        yield url
    finally:
        pg._reset_thread_connection()
        patch.undo()
        _drop()


@pytest.fixture
def pg_conn(pg_database, monkeypatch, tmp_path):
    """A connection to the throwaway database, emptied first.

    app/pg.py pools one psycopg connection per thread, so it is dropped here or a
    test would inherit the previous one's transaction. DB_PATH is repointed at a
    temp path as well, so no code path can reach the real sahakarsetu.db.

    Note that a SET on this connection (TimeZone, say) does not leak into the next
    test: _reset_thread_connection() closes the pooled connection on teardown.
    """
    monkeypatch.setattr(database, "DATABASE_URL", pg_database)
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "never_used.db")
    pg._reset_thread_connection()

    with database.connection() as conn:
        _truncate_all(conn)

    yield database.get_connection()

    pg._reset_thread_connection()


def _truncate_all(conn) -> None:
    """Empty every table the tests write to, leaving the seeded cooperative.

    Deliberately no RESTART IDENTITY: sequences keep climbing across tests, which
    is what makes the lastrowid regression in section E detectable at all. If
    workers and users could land on the same id, a stale lastval() would coincide
    with the right answer and the test would pass for the wrong reason.
    """
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE' "
            "AND table_name <> 'cooperative_federations'"
        )
    ]
    if tables:
        conn.execute(f"TRUNCATE TABLE {', '.join(tables)} CASCADE")


# ── row seeds ────────────────────────────────────────────────────────────────
#
# The raw inserts below are the ones app/auth.py, app/services/booking_flow.py and
# app/kaam.py issue. The _seed_* wrappers give each row its own committed
# transaction, exactly as `with database.connection()` does in the app: seeding
# straight onto the pooled `pg_conn` would leave the implicit transaction
# app/pg.py opened for the INSERT open, and the next `database.connection()` on
# this thread shares that same raw connection -- so a later rollback would
# silently undo the seed.

def _insert_worker(conn, name: str = "Asha Verma", phone: str = "9100000001") -> int:
    return conn.execute(
        "INSERT INTO workers (name, phone, trade, latitude, longitude, status) "
        "VALUES (?, ?, 'plumbing', 23.2, 77.4, 'active')",
        (name, phone),
    ).lastrowid


def _insert_booking(conn, customer_name: str = "Priya Sharma", status: str = "completed") -> int:
    return conn.execute(
        "INSERT INTO bookings (customer_name, trade, latitude, longitude, status) "
        "VALUES (?, 'plumbing', 23.2, 77.4, ?)",
        (customer_name, status),
    ).lastrowid


def _insert_ledger(conn, booking_id: int, worker_id: int | None = None, *,
                   amount: int = 50000, created_at: str | None = None) -> int:
    if created_at is None:
        return conn.execute(
            "INSERT INTO payment_ledger (booking_id, worker_id, party, share_percent, amount_paise) "
            "VALUES (?, ?, 'worker', 80, ?)",
            (booking_id, worker_id, amount),
        ).lastrowid
    return conn.execute(
        "INSERT INTO payment_ledger (booking_id, worker_id, party, share_percent, amount_paise, created_at) "
        "VALUES (?, ?, 'worker', 80, ?, ?)",
        (booking_id, worker_id, amount, created_at),
    ).lastrowid


def _seed_worker(name: str = "Asha Verma", phone: str = "9100000001") -> int:
    with database.connection() as conn:
        return _insert_worker(conn, name, phone)


def _seed_booking(customer_name: str = "Priya Sharma", status: str = "completed") -> int:
    with database.connection() as conn:
        return _insert_booking(conn, customer_name, status)


def _seed_ledger(booking_id: int, worker_id: int | None = None, *,
                 amount: int = 50000, created_at: str | None = None) -> int:
    with database.connection() as conn:
        return _insert_ledger(conn, booking_id, worker_id, amount=amount, created_at=created_at)


def _seed_ledger_today(worker_id: int, created_at: str, amount: int = 100) -> int:
    """A committed ledger row with an explicit timestamp and its own booking.

    UNIQUE (booking_id, party) means each payment needs its own booking, which is
    why this cannot be a loop over one booking id.
    """
    with database.connection() as conn:
        booking_id = _insert_booking(conn, f"Engagement {uuid.uuid4().hex[:6]}")
        return _insert_ledger(conn, booking_id, worker_id, amount=amount, created_at=created_at)


# ── schema comparison helpers ────────────────────────────────────────────────

def _audit_assistant_once() -> None:
    """Run the app's own lazy assistant_audit DDL against the current database.

    app/services/assistant.py:44 creates assistant_audit with CREATE TABLE IF NOT
    EXISTS on every audited turn, so a live SQLite deployment has it even though
    init_db() does not. Calling _audit() gets the real statement instead of a
    copy of it.
    """
    from app.services.assistant import AssistantMessage, _audit

    _audit(
        auth.User(id=1, portal="ghar", name="Priya Sharma", phone="9100000002"),
        AssistantMessage(transcript="who is on duty today"),
        {"intent": "roster", "entities": {}},
        "ok",
    )


def _sqlite_schema(tmp_path) -> dict[str, set[str]]:
    """Table -> column names, from a SQLite database built the way the app builds
    one: `database.init_db()`, then the two tables that are created lazily on
    first use -- `booking_flow_db.ensure_booking_flow_schema()` for the
    booking-flow tables and `assistant._audit()` for assistant_audit. Both run
    real application code, so the baseline is what a live SQLite deployment has
    rather than what init_db() alone produces.

    DATABASE_URL is cleared so init_db() takes its SQLite branch, and DB_PATH is
    the temp file, so the project's real database is never opened.
    """
    patch = pytest.MonkeyPatch()
    path = tmp_path / "sqlite_reference.db"
    try:
        patch.setattr(database, "DATABASE_URL", None)
        patch.setattr(database, "DB_PATH", path)
        database.init_db()
        with database.connection() as conn:
            booking_flow_db.ensure_booking_flow_schema(conn)
        _audit_assistant_once()
    finally:
        patch.undo()

    conn = sqlite3.connect(path)
    try:
        tables = {
            name for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        return {
            table: {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
            for table in tables
        }
    finally:
        conn.close()


def _postgres_schema(conn) -> dict[str, set[str]]:
    """Table -> column names, read from information_schema on a live server.

    This is the check tests/test_database_engine.py cannot do: that test compares
    *text*, so a table or column that exists in only one of the two dialects is
    invisible to it.
    """
    rows = conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema()"
    ).fetchall()
    schema: dict[str, set[str]] = {}
    for table, column in rows:
        schema.setdefault(table, set()).add(column)
    return schema


# ── A. BOOT ──────────────────────────────────────────────────────────────────

def test_init_db_succeeds_as_shipped(pg_database):
    """DEFECT FOUND ON A REAL SERVER, FIXED: the boot blocker is gone.

    app/pg.py used to install `_row_factory(cursor, values)` as
    `raw.row_factory`. That is psycopg 2's two-argument convention; psycopg 3
    calls a row_factory with one argument (the cursor) and expects a row maker
    back (psycopg/cursor.py `_make_row_maker`). So the very first statement on
    any Postgres connection -- the `BEGIN` app/pg.py issues before anything else
    -- raised `TypeError: _row_factory() missing 1 required positional argument:
    'values'`.

    init_db() -> _init_db_postgres() -> executescript() -> _begin_implicit(), so
    it fired during boot, before schema.sql was sent. The Postgres path had
    therefore never executed a single statement, which is why the fake-driver
    tests in test_pg_connection.py all passed.

    This test previously asserted that TypeError, as documentation of a known
    unfixed defect. What it asserts now is the fix: the `pg_database` fixture
    calls the real init_db() with nothing shimmed in, and reaching this test at
    all means it did not raise.
    """
    with database.connection() as conn:
        row = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = 'bookings'"
        ).fetchone()
    assert row is not None, "init_db() reported success but did not create bookings"


def test_init_db_succeeds_once_the_row_factory_call_convention_is_corrected(pg_conn):
    """app/database.py:911 init_db() -> _init_db_postgres(): the production boot.

    Runs with nothing shimmed in, so this measures what init_db() actually does:
    schema.sql applied through app/pg.Connection.executescript(), then
    _upgrade_postgres_columns() and _assert_postgres_schema(). A single rejected
    statement would still kill the service in main.py's lifespan ("Application
    startup failed. Exiting.").
    """
    tables = {row[0] for row in pg_conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
    )}

    for expected in (
        "workers", "users", "sessions", "bookings", "assignments", "declines",
        "payment_ledger", "booking_ratings", "cooperative_federations",
        "worker_documents", "settlements", "disputes", "standard_rates",
        "feedback", "worker_skills", "certifications", "portfolio_items",
        "benefits", "insurance_policies", "grievances", "schema_migrations",
        "assistant_audit", "cooperative",
    ):
        assert expected in tables, f"{expected} is missing from the Postgres boot"

    # _assert_postgres_schema() guards these four by name; a fresh boot must
    # satisfy it without the ALTER TABLE ... ADD COLUMN IF NOT EXISTS fallback
    # having to invent anything.
    assert {"verified", "filename", "byte_size", "content"} <= booking_flow_db.table_columns(
        pg_conn, "worker_documents"
    )

    # init_db() is documented as safe to call repeatedly and _init_db_postgres()
    # runs on every boot, so a second call on an existing schema must not raise.
    database.init_db()


def test_postgres_schema_matches_the_sqlite_schema_after_booking_flow_startup(pg_conn, tmp_path):
    """The cross-dialect check: same tables, same columns, on a real server.

    schema.sql is hand-maintained; database.py's SCHEMA constant plus its ten
    migrations plus the two lazy creators are the SQLite equivalent. They are
    several separate copies of one schema, so the only way to know they still
    agree is to build both and compare.

    Compared after `ensure_booking_flow_schema()` on both sides, i.e. once each
    engine has completed the startup work a live deployment performs -- see
    test_known_defect_postgres_boot_omits_the_columns_ensure_booking_flow_schema_adds
    for the difference that exists before that point.

    Two tables are compared but not asserted equal, because the dialects really do
    differ there:

      - `cooperative` exists only on PostgreSQL. schema.sql:145 calls it a
        "legacy singleton kept as a convenience view over the federation" but
        declares it as a table; the SQLite path never creates it and only reads
        it when backfilling a pre-federation database (app/database.py:564).
      - SQLite's `sqlite_sequence` (created by AUTOINCREMENT) is excluded from the
        baseline because it has no PostgreSQL counterpart by design.

    Everything else must match, or a column silently vanishes on one engine.
    """
    booking_flow_db.ensure_booking_flow_schema(pg_conn)
    pg_schema = _postgres_schema(pg_conn)
    sqlite_schema = _sqlite_schema(tmp_path)

    only_sqlite = sorted(set(sqlite_schema) - set(pg_schema))
    assert only_sqlite == [], f"tables the SQLite path creates that Postgres does not: {only_sqlite}"

    only_postgres = sorted(set(pg_schema) - set(sqlite_schema))
    assert only_postgres == ["cooperative"], (
        f"unexpected tables on Postgres that the SQLite path does not create: {only_postgres}"
    )

    drift = {
        table: {
            "only_on_sqlite": sorted(sqlite_schema[table] - pg_schema.get(table, set())),
            "only_on_postgres": sorted(pg_schema.get(table, set()) - sqlite_schema[table]),
        }
        for table in sorted(sqlite_schema)
        if sqlite_schema[table] != pg_schema.get(table, set())
    }
    # Only "missing on Postgres" is drift. A column Postgres has and SQLite does
    # not is fine and in one case expected: `assignments.allocation_score`.
    # _pending_changes adds it only when no score column exists at all, and
    # SQLite's SCHEMA already declares `assignments.score`, so the SQLite path
    # never grows it while schema.sql declares both for a legacy-shaped database.
    missing_on_postgres = {
        table: detail["only_on_sqlite"]
        for table, detail in drift.items()
        if detail["only_on_sqlite"]
    }
    assert missing_on_postgres == {}, (
        f"columns the SQLite path creates that Postgres does not: {missing_on_postgres}"
    )
    unexpected_extra = {
        table: detail["only_on_postgres"]
        for table, detail in drift.items()
        if detail["only_on_postgres"] != (["allocation_score"] if table == "assignments" else [])
    }
    assert unexpected_extra == {}, (
        f"unexpected columns on Postgres: {unexpected_extra}"
    )


def test_known_defect_postgres_boot_omits_the_columns_ensure_booking_flow_schema_adds(
    pg_conn, tmp_path
):
    """KNOWN UNFIXED DEFECT -- the two engines do not have the same schema at boot.

    SQLite's init_db() ends up with five columns that PostgreSQL's init_db() does
    not create:

        assignments.score_breakdown, assignments.explanation,
        bookings.completed_at, workers.base_rating, workers.rating_count

    On SQLite those come from the migration chain; on PostgreSQL
    `_init_db_postgres()` applies schema.sql and does not run migrate()
    (app/database.py:937), and schema.sql does not declare them. They only appear
    once a request reaches `booking_flow_db.ensure_booking_flow_schema()`, which
    ALTERs them in one at a time (app/booking_flow_db.py:148-171). Verified on a
    live server: calling it adds all five, and no others.

    So between boot and the first booking-flow request the two engines disagree,
    and anything that reads those columns on PostgreSQL fails with
    UndefinedColumn until a booking-flow request has happened. app/pg.py cannot
    fix this -- it is a missing schema.sql declaration.

    Order-independent: the columns are dropped first, since an earlier test in
    this module may already have caused ensure_booking_flow_schema() to run.
    """
    for table, column in (
        ("assignments", "score_breakdown"),
        ("assignments", "explanation"),
        ("bookings", "completed_at"),
        ("workers", "base_rating"),
        ("workers", "rating_count"),
    ):
        pg_conn.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column}")

    pg_schema = _postgres_schema(pg_conn)
    sqlite_schema = _sqlite_schema(tmp_path)

    drift = {
        table: sorted(sqlite_schema[table] - pg_schema.get(table, set()))
        for table in sorted(sqlite_schema)
        if sqlite_schema[table] - pg_schema.get(table, set())
    }
    assert drift == {
        "assignments": ["explanation", "score_breakdown"],
        "bookings": ["completed_at"],
        "workers": ["base_rating", "rating_count"],
    }, (
        f"the boot-time schema difference changed; new drift to triage: {drift}"
    )


def test_payment_ledger_check_and_unique_constraints_exist_on_postgres(pg_conn):
    """app/booking_flow_db.py:23 declares payment_ledger in SQLite dialect.

    SQLite enforces those CHECKs inline; PostgreSQL has to, and a boot that
    silently skipped them would let a negative payout or a duplicate
    (booking_id, party) settle through. The UNIQUE pair is what makes a replayed
    settlement idempotent, so it is asserted behaviourally as well.
    """
    booking_id = _seed_booking()
    worker_id = _seed_worker()
    _seed_ledger(booking_id, worker_id)

    # UNIQUE (booking_id, party): a replayed settlement must insert nothing.
    with pytest.raises(sqlite3.IntegrityError):
        with database.connection() as conn:
            _insert_ledger(conn, booking_id, worker_id, amount=1)
    assert pg_conn.execute(
        "SELECT COUNT(*) FROM payment_ledger WHERE booking_id = ? AND party = 'worker'",
        (booking_id,),
    ).fetchone()[0] == 1

    # CHECK (party IN ('worker', 'welfare_fund', 'platform_operations'))
    with pytest.raises(sqlite3.IntegrityError):
        with database.connection() as conn:
            conn.execute(
                "INSERT INTO payment_ledger (booking_id, party, share_percent, amount_paise) "
                "VALUES (?, 'landlord', 10, 100)",
                (booking_id,),
            )

    # CHECK (amount_paise >= 0)
    with pytest.raises(sqlite3.IntegrityError):
        with database.connection() as conn:
            conn.execute(
                "INSERT INTO payment_ledger (booking_id, party, share_percent, amount_paise) "
                "VALUES (?, 'welfare_fund', 10, -1)",
                (booking_id,),
            )


def test_booking_ratings_check_and_unique_constraints_exist_on_postgres(pg_conn):
    """app/booking_flow_db.py:36 declares booking_ratings in SQLite dialect.

    Same reasoning as payment_ledger: one rating per booking (UNIQUE booking_id)
    and a rating outside 1..5 must not survive the dialect change.
    """
    booking_id = _seed_booking()
    worker_id = _seed_worker()
    pg_conn.execute(
        "INSERT INTO booking_ratings (booking_id, worker_id, rating) VALUES (?, ?, 5)",
        (booking_id, worker_id),
    ).lastrowid

    with pytest.raises(sqlite3.IntegrityError):  # UNIQUE (booking_id)
        with database.connection() as conn:
            conn.execute(
                "INSERT INTO booking_ratings (booking_id, worker_id, rating) VALUES (?, ?, 3)",
                (booking_id, worker_id),
            )

    other_booking = _seed_booking("Priya Sharma II")
    with pytest.raises(sqlite3.IntegrityError):  # CHECK (rating BETWEEN 1 AND 5)
        with database.connection() as conn:
            conn.execute(
                "INSERT INTO booking_ratings (booking_id, worker_id, rating) VALUES (?, ?, 9)",
                (other_booking, worker_id),
            )


# ── B. TRANSLATED SQL ────────────────────────────────────────────────────────
#
# One test per statement form found by grepping app/. Each runs the statement the
# application actually issues, through app/pg.py, against real rows.

def test_datetime_now_with_a_bound_interval_modifier(pg_conn):
    """app/services/overview.py:373 counts stale settlements.

        SELECT COUNT(*) FROM settlements WHERE status IN ('proposed', 'countered')
          AND COALESCE(responded_at, created_at) <= datetime('now', ?)

    bound with '-24 hours'. app/pg rewrites it to NOW() + CAST(%s AS INTERVAL);
    SQLite's modifier *is* interval syntax, so the string casts directly. A
    30-hour-old settlement must be counted, a 5-minute-old one must not.

    Two settlements, so two bookings: settlements has UNIQUE (booking_id).
    """
    worker_id = _seed_worker()
    now = dt.datetime.now(dt.timezone.utc)
    stale, fresh = (now - dt.timedelta(hours=30)).isoformat(), (now - dt.timedelta(minutes=5)).isoformat()

    for created_at in (stale, fresh):
        with database.connection() as conn:
            booking_id = _insert_booking(conn, status="completed")
            conn.execute(
                "INSERT INTO settlements (booking_id, worker_id, hours_worked, standard_paise, "
                "proposed_paise, created_at) VALUES (?, ?, 2, 1000, 2000, ?)",
                (booking_id, worker_id, created_at),
            )

    waiting = pg_conn.execute(
        "SELECT COUNT(*) FROM settlements WHERE status IN ('proposed', 'countered') "
        "AND COALESCE(responded_at, created_at) <= datetime('now', ?)",
        ("-24 hours",),
    ).fetchone()[0]

    assert waiting == 1, "only the 30-hour-old settlement is past the 24-hour mark"


def test_datetime_on_a_column_compared_against_a_bound_iso_string(pg_conn):
    """app/services/overview.py:521/524/528 normalise a stored timestamp.

        WHERE cooperative_id = ? AND datetime(created_at) >= ?

    bound with month_start.isoformat(), a *string*, even though the column is
    TIMESTAMPTZ on PostgreSQL. app/pg turns datetime(col) into col; the open
    question is whether PostgreSQL will compare a timestamptz against a bound text
    parameter or reject the text. Fixed timestamps rather than "now", so the
    result cannot depend on which day of the month this runs on.
    """
    worker_id = _seed_worker()
    _seed_ledger(_seed_booking(), worker_id, amount=100, created_at="2026-02-10T09:00:00+00:00")
    _seed_ledger(_seed_booking("Outside"), worker_id, amount=999, created_at="2026-01-10T09:00:00+00:00")

    payout = pg_conn.execute(
        "SELECT COALESCE(SUM(amount_paise),0) FROM payment_ledger WHERE cooperative_id = ? "
        "AND party = 'worker' AND datetime(created_at) >= ?",
        (1, "2026-02-01"),
    ).fetchone()[0]

    assert payout == 100, f"expected only the February row, got {payout}"


def test_date_with_a_modifier_inside_count_distinct(pg_conn):
    """app/kaam.py:162-170 and app/services/booking_flow.py:396 count IST days.

        COUNT(DISTINCT DATE(created_at, '+330 minutes')) AS engagement_days

    '+330 minutes' is IST. The SQLite data is naive UTC text, so adding the offset
    is how the app converts a UTC column to an IST calendar day. The session
    TimeZone is pinned to UTC here so the conversion happens exactly once -- see
    test_known_defect_date_with_modifier_double_shifts_on_a_non_utc_server for
    what happens when it does not.

    Three payments at 03:00, 10:00 and 13:00 UTC are 08:30, 15:30 and 18:30 IST,
    all on one IST calendar day, so engagement_days must be 1.
    """
    worker_id = _seed_worker()
    pg_conn.execute("SET TIME ZONE 'UTC'")

    noon_utc = dt.datetime.now(dt.timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    for hours in (-9, -2, 1):
        _seed_ledger_today(worker_id, (noon_utc + dt.timedelta(hours=hours)).isoformat())

    row = pg_conn.execute(
        "SELECT COUNT(*) AS completed_jobs, "
        "COUNT(DISTINCT DATE(created_at, '+330 minutes')) AS engagement_days "
        "FROM payment_ledger WHERE party = 'worker' AND worker_id = ? AND cooperative_id = ?",
        (worker_id, 1),
    ).fetchone()

    assert row["completed_jobs"] == 3
    assert row["engagement_days"] == 1, "three payments on one IST day are one engagement day"


def test_known_defect_date_with_modifier_double_shifts_on_a_non_utc_server(pg_conn):
    """KNOWN UNFIXED DEFECT -- the IST shift is applied twice off UTC.

    `DATE(created_at, '+330 minutes')` assumes created_at is a naive UTC *string*,
    which is what SQLite stores. On PostgreSQL it is TIMESTAMPTZ, so
    `created_at + INTERVAL '330 minutes'` shifts an absolute instant, and
    `::date` then truncates it in the *session* TimeZone. If the session TimeZone
    is not UTC the offset has already been accounted for by the cast, and adding
    it again moves the value into the next day.

    app/pg.py never issues a SET TIME ZONE, so the bucketing silently depends on
    whatever the server default is. This Homebrew server defaults to
    Asia/Kolkata; a managed host such as Neon defaults to UTC, which is why the
    same code would produce different engagement counts in development and
    production. Pinned explicitly so the result does not depend on the host.

    `SET` is not parameterised in PostgreSQL, hence the literal.
    """
    worker_id = _seed_worker()
    pg_conn.execute("SET TIME ZONE 'Asia/Kolkata'")

    noon_utc = dt.datetime.now(dt.timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    for hours in (-9, -2, 1):
        _seed_ledger_today(worker_id, (noon_utc + dt.timedelta(hours=hours)).isoformat())

    row = pg_conn.execute(
        "SELECT COUNT(*) AS completed_jobs, "
        "COUNT(DISTINCT DATE(created_at, '+330 minutes')) AS engagement_days "
        "FROM payment_ledger WHERE party = 'worker' AND worker_id = ? AND cooperative_id = ?",
        (worker_id, 1),
    ).fetchone()

    assert row["completed_jobs"] == 3
    # The 13:00 UTC payment lands at 18:30 IST, +330 minutes pushes it to
    # midnight, and ::date rolls it into the next day. Wrong bucket, no error.
    assert row["engagement_days"] == 2, (
        "expected the double shift to split one IST day into two; if this now "
        "returns 1 the TimeZone dependence has been fixed and this test should go"
    )


def test_two_arg_max_becomes_greatest_on_postgres(pg_conn):
    """app/kaam.py:375 decrements a worker's weekly load when a job is declined.

        UPDATE workers SET jobs_this_week = MAX(0, jobs_this_week - 1) WHERE id = ?

    Two-argument MAX is SQLite's scalar max; PostgreSQL spells that GREATEST and
    has no two-arg MAX at all. The clamp at zero is the behaviour worth pinning:
    the counter must not go negative.
    """
    worker_id = _seed_worker()
    with database.connection() as conn:
        conn.execute("UPDATE workers SET jobs_this_week = ? WHERE id = ?", (3, worker_id))
        conn.execute(
            "UPDATE workers SET jobs_this_week = MAX(0, jobs_this_week - 1) WHERE id = ?",
            (worker_id,),
        )
    assert pg_conn.execute(
        "SELECT jobs_this_week FROM workers WHERE id = ?", (worker_id,)
    ).fetchone()[0] == 2

    # Drive it to the clamp, then one step past it.
    with database.connection() as conn:
        conn.execute("UPDATE workers SET jobs_this_week = 0 WHERE id = ?", (worker_id,))
        conn.execute(
            "UPDATE workers SET jobs_this_week = MAX(0, jobs_this_week - 1) WHERE id = ?",
            (worker_id,),
        )
    assert pg_conn.execute(
        "SELECT jobs_this_week FROM workers WHERE id = ?", (worker_id,)
    ).fetchone()[0] == 0


def test_insert_or_ignore_twice_is_a_no_op_on_the_second_insert(pg_conn):
    """app/rates.py:79 seeds the rate card idempotently.

        INSERT OR IGNORE INTO standard_rates (trade, cooperative_id, ...) VALUES (?)

    app/pg rewrites this to ON CONFLICT DO NOTHING. standard_rates has a
    composite primary key (trade, cooperative_id) and no `id` column, so this is
    also the case where appending RETURNING id would be a syntax error. The second
    insert must change nothing and must not raise.
    """
    sql = (
        "INSERT OR IGNORE INTO standard_rates "
        "(trade, cooperative_id, visit_charge_paise, hourly_rate_paise, min_hours, band_percent) "
        "VALUES (?, ?, ?, ?, ?, ?)"
    )
    params = ("plumbing", 1, 10000, 50000, 1.0, 25)

    with database.connection() as conn:
        conn.execute(sql, params)
    assert pg_conn.execute("SELECT COUNT(*) FROM standard_rates").fetchone()[0] == 1

    with database.connection() as conn:
        second = conn.execute(sql, params)
    assert pg_conn.execute("SELECT COUNT(*) FROM standard_rates").fetchone()[0] == 1
    # Nothing was inserted, so there is no id to report -- not the first row's.
    assert second.lastrowid is None


def test_pragma_table_info_shape_and_sqlite_master_existence_probe(pg_conn):
    """The two introspection shapes app/ relies on.

    app/booking_flow_db.py:112 `table_columns()` reads row["name"] out of
    `PRAGMA table_info(x)`, and app/booking_flow_db.py:123 plus
    app/services/overview.py:227 probe existence with
    `SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?`.

    SQLite's PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk);
    app/pg substitutes a one-column projection of information_schema. What matters
    is that the one column app/ reads is right and that the probe answers yes and
    no correctly; the shape is asserted below to document it.
    """
    columns = booking_flow_db.table_columns(pg_conn, "payment_ledger")
    assert {"id", "booking_id", "worker_id", "party", "amount_paise"} <= columns

    # One column wide, not six. Documented, not a requirement: nothing in app/
    # reads the other five.
    assert all(row.keys() == ["name"] for row in pg_conn.execute("PRAGMA table_info(workers)"))

    assert booking_flow_db.pick_column(
        pg_conn, "workers", booking_flow_db.WORKER_NAME_COLUMNS
    ) == "name"
    assert booking_flow_db.pick_column(pg_conn, "workers", ("nonexistent_column",)) is None

    present = pg_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", ("bookings",)
    ).fetchone()
    absent = pg_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", ("no_such_table",)
    ).fetchone()
    assert present is not None and present[0] == 1
    assert absent is None


def test_like_with_a_bound_pattern_containing_a_percent(pg_conn):
    """app/main.py:453/458 search with a bound pattern built as f"%{needle}%".

    A literal `%` in the statement *text* would be read as a psycopg format
    specifier once parameters are supplied, so app/pg doubles it. The bug this
    catches is the opposite one: doubling too eagerly would turn the pattern's
    own wildcards into literals and silently match nothing. A percent in the
    *data* must not need escaping in the parameter either.
    """
    for name in ("Asha Verma", "Kamla Devi"):
        _seed_worker(name=name)

    found = pg_conn.execute(
        "SELECT name FROM workers WHERE LOWER(name) LIKE ? ORDER BY name", ("%verma%",)
    ).fetchall()
    assert [row[0] for row in found] == ["Asha Verma"], "the bound % must stay a wildcard"

    assert pg_conn.execute(
        "SELECT COUNT(*) FROM workers WHERE LOWER(name) LIKE ?", ("%nobody%",)
    ).fetchone()[0] == 0

    with database.connection() as conn:
        conn.execute(
            "INSERT INTO users (portal, phone, name, password_hash) "
            "VALUES ('ghar', '9111111111', 'Discount 50% Club', 'x')"
        )
    # '50%' here is literal "50" followed by a wildcard.
    assert pg_conn.execute(
        "SELECT COUNT(*) FROM users WHERE name LIKE ?", ("Discount 50%",)
    ).fetchone()[0] == 1


# ── C. TRANSACTIONS ──────────────────────────────────────────────────────────

def test_connection_is_atomic_and_rolls_back_when_the_block_raises(pg_conn):
    """The autocommit=True regression: database.connection() is all-or-nothing.

    app/pg.py runs the raw psycopg connection with autocommit=True, so nothing
    opens a transaction unless app/pg does. If the wrapper did not open one on
    the first INSERT, this row would be committed the moment the statement
    returned and the raise below would arrive too late to undo it -- which is
    what would leave half a signup in the database.
    """
    with pytest.raises(RuntimeError, match="boom"):
        with database.connection() as conn:
            conn.execute(
                "INSERT INTO workers (name, trade, latitude, longitude) "
                "VALUES ('Half Written', 'plumbing', 23.2, 77.4)"
            )
            raise RuntimeError("boom")

    assert pg_conn.execute(
        "SELECT COUNT(*) FROM workers WHERE name = 'Half Written'"
    ).fetchone()[0] == 0, "the INSERT was committed despite the exception"


def test_connection_commits_every_insert_in_the_block(pg_conn):
    """The positive half of C: a block that completes must persist all of it.

    Two rows, not one: a wrapper that deferred the BEGIN until the second
    statement, or that committed on the first, would pass a single-insert test
    while still breaking multi-statement units of work like signup.
    """
    with database.connection() as conn:
        worker_id = conn.execute(
            "INSERT INTO workers (name, trade, latitude, longitude) "
            "VALUES ('Committed', 'plumbing', 23.2, 77.4) RETURNING id"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO users (portal, phone, name, password_hash, worker_id) "
            "VALUES ('kaam', '9122222222', 'Committed', 'x', ?)",
            (worker_id,),
        )

    assert pg_conn.execute("SELECT COUNT(*) FROM workers WHERE name = 'Committed'").fetchone()[0] == 1
    assert pg_conn.execute("SELECT COUNT(*) FROM users WHERE phone = '9122222222'").fetchone()[0] == 1


# ── D. BEGIN IMMEDIATE ───────────────────────────────────────────────────────

def test_open_connection_returns_the_postgres_wrapper_on_postgres(pg_conn):
    """app/booking_flow_db.py:57 open_connection() must not fall back to SQLite.

    It branches on `isinstance(conn, sqlite3.Connection)` to decide whether to
    apply the SQLite-only tuning. On PostgreSQL that branch is skipped, so what
    it returns has to be the psycopg-backed wrapper -- otherwise the booking flow
    would quietly open a local file while the rest of the app uses Postgres,
    which is exactly the failure that lost production data once.
    """
    conn = booking_flow_db.open_connection()
    try:
        assert isinstance(conn, pg.Connection)
        assert not isinstance(conn, sqlite3.Connection)
        assert database.active_engine() == "postgresql"
        assert database.get_database_engine_info()["engine"] == "PostgreSQL"
        assert {"id", "status"} <= booking_flow_db.table_columns(conn, "bookings")
    finally:
        conn.close()


def test_immediate_transaction_commits_on_success_and_rolls_back_on_exception(pg_conn):
    """app/booking_flow_db.py:94 immediate_transaction(): all-or-nothing.

    Every booking-flow write goes through this block. It issues BEGIN IMMEDIATE
    explicitly, so unlike database.connection() it relies on the caller's own
    COMMIT/ROLLBACK rather than on a wrapper-managed transaction.
    """
    booking_flow_db.ensure_booking_flow_schema(pg_conn)

    with booking_flow_db.immediate_transaction(pg_conn):
        _insert_booking(pg_conn, "Committed Flow")
    assert pg_conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE customer_name = 'Committed Flow'"
    ).fetchone()[0] == 1

    with pytest.raises(RuntimeError, match="boom"):
        with booking_flow_db.immediate_transaction(pg_conn):
            _insert_booking(pg_conn, "Rolled Back Flow")
            raise RuntimeError("boom")
    assert pg_conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE customer_name = 'Rolled Back Flow'"
    ).fetchone()[0] == 0


def test_immediate_transaction_holds_a_write_lock_a_second_connection_cannot_take(
    pg_database, pg_conn
):
    """BEGIN IMMEDIATE's whole purpose is to serialise writers.

    Plain BEGIN is deferred in PostgreSQL and takes no lock, so without app/pg's
    transaction-scoped advisory lock two requests could both read a booking as
    'pending' and assign it twice. SQLite gives exactly one writer at a time;
    this asserts the equivalent three ways: the advisory lock is visible in
    pg_locks, a second connection cannot take it without waiting, and the blocking
    acquisition really does block (it hits lock_timeout).

    Note the `?` placeholder in the pg_locks probe: that statement goes through
    app/pg, which rewrites `?` to psycopg's `%s` and doubles any literal `%`. A
    hand-written `%s` would arrive as `%%s` and fail with "the query has 0
    placeholders but 1 parameters were passed".
    """
    booking_flow_db.ensure_booking_flow_schema(pg_conn)
    lock_key = pg._BOOKING_FLOW_LOCK_KEY

    holder_state: dict[str, object] = {}
    started = threading.Event()
    release = threading.Event()
    holder_errors: list[BaseException] = []

    def hold() -> None:
        # A thread of its own: app/pg pools one psycopg connection per thread, so
        # a second wrapper on this thread would share the very lock under test.
        started.set()
        try:
            with booking_flow_db.immediate_transaction(database.get_connection()) as conn:
                holder_state["pid"] = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
                holder_state["holding"] = True
                _insert_booking(conn, "Locked Flow")
                # Hold the writer lock until the probes below have run. Without
                # this the block ends -- and releases the lock -- before the
                # second connection is even opened, which would make the probe
                # vacuously pass. Bounded, so a bug cannot wedge the thread.
                release.wait(20)
        except BaseException as exc:  # noqa: BLE001 - reported on the main thread
            holder_errors.append(exc)

    holder = threading.Thread(target=hold, daemon=True)
    holder.start()
    assert started.wait(5)

    try:
        deadline = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=10)
        lock_rows = 0
        while dt.datetime.now(dt.timezone.utc) < deadline:
            with database.connection() as probe:
                lock_rows = probe.execute(
                    "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = ?",
                    (holder_state.get("pid"),),
                ).fetchone()[0]
            if lock_rows:
                break
            assert not holder_errors, f"the holding thread failed: {holder_errors}"

        assert not holder_errors, f"the holding thread failed: {holder_errors}"
        assert holder_state.get("holding") is True, "the holding transaction ended too early"
        assert lock_rows >= 1, "no advisory lock row in pg_locks for the holding backend"

        with psycopg.connect(pg_database, autocommit=True) as second:
            assert second.execute(
                "SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)
            ).fetchone()[0] is False, "a second connection took the writer lock"

            second.execute("SET lock_timeout = '500ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                second.execute("SELECT pg_advisory_xact_lock(%s)", (lock_key,))
    finally:
        release.set()
        holder.join(timeout=15)

    assert not holder.is_alive(), "the holder never released its transaction"
    assert not holder_errors, f"the holding thread failed: {holder_errors}"
    assert pg_conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE customer_name = 'Locked Flow'"
    ).fetchone()[0] == 1

    # xact-scoped: the lock went with the transaction, so it is available again.
    with psycopg.connect(pg_database, autocommit=True) as second:
        assert second.execute("SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)).fetchone()[0] is True


# ── E. lastrowid ─────────────────────────────────────────────────────────────

def test_lastrowid_matches_the_real_id_for_workers_and_users(pg_conn):
    """The lastval() regression: lastrowid must be this statement's own id.

    lastval() is session-scoped and table-agnostic, so on a pooled connection it
    returns whatever the *previous* statement's sequence produced -- another
    request's id, or another table's. app/pg reads it from RETURNING id instead.

    pg_conn deliberately does not reset identity between tests, so workers and
    users land on different ids and a stale lastval() cannot coincide with the
    right answer; that is asserted explicitly at the end. Each id is also fetched
    back independently rather than trusting lastrowid's own round trip.
    """
    worker_last = pg_conn.execute(
        "INSERT INTO workers (name, trade, latitude, longitude) "
        "VALUES ('Lastrowid Worker', 'plumbing', 23.2, 77.4)"
    ).lastrowid
    worker_real = pg_conn.execute(
        "SELECT id FROM workers WHERE name = 'Lastrowid Worker'"
    ).fetchone()[0]
    assert worker_last == worker_real, f"lastrowid {worker_last} != real id {worker_real}"

    user_last = pg_conn.execute(
        "INSERT INTO users (portal, phone, name, password_hash, worker_id) "
        "VALUES ('kaam', '9133333333', 'Lastrowid User', 'x', ?)",
        (worker_real,),
    ).lastrowid
    user_real = pg_conn.execute(
        "SELECT id FROM users WHERE phone = '9133333333'"
    ).fetchone()[0]
    assert user_last == user_real, f"lastrowid {user_last} != real id {user_real}"

    assert worker_real != user_real, (
        "workers and users landed on the same id, so this test cannot distinguish "
        "a correct lastrowid from a stale lastval()"
    )


def test_lastrowid_is_none_for_a_table_with_no_id_column(pg_conn):
    """sessions has no `id` -- its primary key is token_hash.

    lastval() would answer with whatever the previous INSERT on this pooled
    connection left behind, so app/pg's _add_returning_id() has to avoid the
    problem two ways and both are asserted here: no `RETURNING id` is appended
    (a syntax error otherwise), and lastrowid is None rather than the stale
    value. The stale value is made concrete first, so the None means something.
    """
    stale = pg_conn.execute(
        "INSERT INTO users (portal, phone, name, password_hash) "
        "VALUES ('ghar', '9144444444', 'Stale Source', 'x')"
    ).lastrowid
    assert stale is not None, "precondition: a real id to go stale"

    cursor = pg_conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (
            "tok_" + uuid.uuid4().hex,
            stale,
            (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat(),
        ),
    )

    assert cursor.lastrowid is None, (
        f"lastrowid leaked the previous INSERT's id ({stale}) for a table with no id column"
    )
    assert pg_conn.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1


# ── timestamps come back exactly as SQLite produced them ─────────────────────
#
# Regression section, and the reason it reads the way it does. schema.sql
# declares TIMESTAMP WITH TIME ZONE, so psycopg hands back dt.datetime, but this
# app was written against SQLite where those columns are TEXT and every one of
# ~47 call sites parses a 'YYYY-MM-DD HH:MM:S' string. Against a live server the
# mismatch showed up as:
#
#   - overview._parse raising TypeError (datetime.replace's first two positional
#     parameters are year and month, so `.replace("T", " ")` never reached strptime)
#   - 21 Pydantic models declaring these fields `str` failing validation, since
#     v2 does not coerce datetime into str
#   - app/services/ledger.py feeding str(created_at) into a SHA-256 hash chain, so
#     the same booking produced a DIFFERENT DIGEST -- silent corruption of the
#     settlement audit trail rather than an error
#
# The fix is in the Row wrapper, because that is the "Postgres behind the sqlite3
# surface" layer: naive-UTC text, byte-identical to the SQLite deployment.

SQLITE_TIMESTAMP = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"


def test_timestamptz_columns_come_back_as_sqlite_spelled_strings(pg_conn):
    """Row must hand back 'YYYY-MM-DD HH:MM:SS', not datetime."""
    booking_id = _seed_booking()
    worker_id = _seed_worker()
    ledger_id = _seed_ledger(booking_id, worker_id)

    values = {
        "bookings.created_at": pg_conn.execute(
            "SELECT created_at FROM bookings WHERE id = ?", (booking_id,)
        ).fetchone()[0],
        "payment_ledger.created_at": pg_conn.execute(
            "SELECT created_at FROM payment_ledger WHERE id = ?", (ledger_id,)
        ).fetchone()[0],
    }

    for label, value in values.items():
        assert isinstance(value, str), (
            f"{label} came back as {type(value).__name__}; every timestamp consumer "
            "in app/ parses a string"
        )
        assert re.fullmatch(SQLITE_TIMESTAMP, value), (
            f"{label} is {value!r}, not SQLite's CURRENT_TIMESTAMP spelling"
        )


def test_the_utc_timezone_is_pinned_on_every_pooled_connection(pg_conn):
    """The session TimeZone decides what `::date` truncates to.

    `DATE(created_at, '+330 minutes')` (app/kaam.py:162-170) becomes
    `((created_at + interval)::date)`. On a timestamptz column that truncates in
    the SESSION zone, and nothing set it: this machine defaults to Asia/Kolkata
    while Neon defaults to UTC, so three payments on one IST day counted as two,
    with no error and different numbers in each environment.
    """
    zone = pg_conn.execute("SHOW TIMEZONE").fetchone()[0]
    assert zone.upper() == "UTC", (
        f"session TimeZone is {zone!r}; date bucketing would differ between a local "
        "server and Neon (UTC)"
    )


def test_ist_bucketing_counts_the_right_day(pg_conn):
    """Regression for the silent double-shift found on a live server.

    Three payments inside one IST day must all fall in that IST day.
    UNIQUE (booking_id, party) permits one worker row per booking, so this uses
    three bookings and scopes the count to the amounts it inserted.
    """
    worker_id = _seed_worker()
    ist_day = dt.datetime(2026, 3, 14, tzinfo=dt.timezone.utc)

    # 05:30, 11:30 and 23:30 IST on 14 March -- all one IST day.
    for offset, hour in enumerate((0, 6, 18)):
        booking_id = _seed_booking()
        pg_conn.execute(
            "INSERT INTO payment_ledger "
            "(booking_id, worker_id, party, share_percent, amount_paise, created_at) "
            "VALUES (?, ?, 'worker', 100, ?, ?)",
            (booking_id, worker_id, 900000 + offset, ist_day + dt.timedelta(hours=hour)),
        )
    pg_conn.commit()

    counted = pg_conn.execute(
        "SELECT COUNT(*) FROM payment_ledger WHERE amount_paise >= 900000 "
        "AND (created_at + CAST('+330 minutes' AS INTERVAL))::date = '2026-03-14'"
    ).fetchone()[0]
    assert counted == 3, f"IST day bucketing kept {counted} of 3 payments"


def test_overview_parse_helper_accepts_a_postgres_timestamp(pg_conn):
    """app/services/overview.py:_parse is the first consumer to choke."""
    from app.services.overview import _parse

    booking_id = _seed_booking()
    raw = pg_conn.execute(
        "SELECT created_at FROM bookings WHERE id = ?", (booking_id,)
    ).fetchone()[0]

    parsed = _parse(raw)
    assert parsed is not None


def test_str_typed_pydantic_timestamp_fields_validate(pg_conn):
    """21 models declare these fields `str`; v2 does not coerce datetime."""
    from app.profile import WorkerDocumentOut

    booking_id = _seed_booking()
    worker_id = _seed_worker()
    pg_conn.execute(
        "INSERT INTO worker_documents (worker_id, document_type, file_url) "
        "VALUES (?, 'id_proof', 'ref://x')",
        (worker_id,),
    )
    pg_conn.commit()

    row = pg_conn.execute(
        "SELECT id, worker_id, document_type, file_url, uploaded_at, cooperative_id, "
        "verified, verified_by, verified_at, rejection_reason, filename, "
        "content_type, byte_size, content IS NOT NULL AS has_content "
        "FROM worker_documents"
    ).fetchone()

    model = WorkerDocumentOut.model_validate(dict(row))
    assert isinstance(model.uploaded_at, str)


def test_ledger_hash_is_identical_across_engines(pg_conn, tmp_path):
    """The reason timestamps are strings and not datetimes.

    app/services/ledger.py hashes str(created_at) into a SHA-256 chain. When the
    value was a datetime the same booking hashed differently on Postgres than on
    SQLite -- a silent divergence in the settlement audit trail.
    """
    import sqlite3 as sq

    worker_id = _seed_worker()
    created_at = dt.datetime(2026, 3, 14, 9, 30, tzinfo=dt.timezone.utc)

    pg_conn.execute(
        "UPDATE workers SET created_at = ? WHERE id = ?", (created_at, worker_id)
    )
    pg_conn.commit()
    pg_value = pg_conn.execute(
        "SELECT created_at FROM workers WHERE id = ?", (worker_id,)
    ).fetchone()[0]

    # Same instant, written by SQLite's own CURRENT_TIMESTAMP spelling.
    sqlite_path = tmp_path / "ledger.db"
    conn = sq.connect(sqlite_path)
    conn.executescript(
        "CREATE TABLE workers (id INTEGER PRIMARY KEY, name TEXT, trade TEXT, "
        "latitude REAL, longitude REAL, created_at TEXT)"
    )
    conn.execute(
        "INSERT INTO workers VALUES (?, 'Meena', 'plumbing', 23.2, 77.4, ?)",
        (worker_id, pg_value),
    )
    conn.commit()
    sqlite_value = conn.execute(
        "SELECT created_at FROM workers WHERE id = ?", (worker_id,)
    ).fetchone()[0]
    conn.close()

    assert pg_value == sqlite_value, (
        "the Postgres spelling must match SQLite byte-for-byte or the ledger hash "
        "chain diverges between deployments"
    )
    assert hashlib.sha256(pg_value.encode()).hexdigest() == hashlib.sha256(
        sqlite_value.encode()
    ).hexdigest()


def test_list_documents_returns_has_content_without_fetching_the_bytes(pg_conn):
    """The listing projects has_content in SQL, so the BYTEA never crosses the wire."""
    import app.profile as profile
    import app.tenancy as tenancy

    worker_id = _seed_worker()
    pg_conn.execute(
        "INSERT INTO worker_documents "
        "(worker_id, document_type, file_url, filename, content_type, byte_size, content) "
        "VALUES (?, 'id_proof', 'ref://x', 'aadhaar.pdf', 'application/pdf', 4, ?)",
        (worker_id, b"\x00\x01\x02\x03"),
    )
    pg_conn.commit()

    previous = tenancy.tenant_id
    tenancy.tenant_id = lambda: 1
    try:
        docs = profile.list_documents(worker_id)
    finally:
        tenancy.tenant_id = previous

    assert docs, "no documents returned"
    assert docs[0].has_content is True
    assert not hasattr(docs[0], "content"), "the bytes must never reach the response model"


def test_document_content_endpoint_still_returns_the_bytes(pg_conn):
    """The one query that genuinely needs the blob must still fetch it."""
    import app.profile as profile

    worker_id = _seed_worker()
    pg_conn.execute(
        "INSERT INTO worker_documents (worker_id, document_type, file_url, content) "
        "VALUES (?, 'id_proof', 'ref://x', ?)",
        (worker_id, b"\x00\x01\x02\x03"),
    )
    pg_conn.commit()

    document_id = pg_conn.execute(
        "SELECT id FROM worker_documents WHERE worker_id = ?", (worker_id,)
    ).fetchone()[0]
    stored = profile.document_content(document_id)
    assert stored is not None
    data, _content_type, _filename = stored
    assert data == b"\x00\x01\x02\x03"


def test_auth_signup_completes_on_postgres(pg_conn):
    """auth.signup() 500'd here because User.created_at is `str | None`.

    `_user()` runs outside the `with connection()` block, so the failure left the
    worker and users rows committed and no session token issued -- on every
    sign-up, sign-in and authenticated read.
    """
    request = auth.SignupRequest(
        portal="kaam", name="Asha Verma", phone="9155555555",
        password="secret12", trade="plumbing", locality="Bhopal",
    )
    user = auth.signup(request)

    assert user.portal == "kaam"
    assert isinstance(user.created_at, (str, type(None)))
    # The rows exist exactly once, and signup did not double-insert.
    assert pg_conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_init_db_converges_an_existing_older_database(pg_database):
    """The production case: Neon already exists and predates this schema.sql.

    Found by running it. schema.sql creates indexes over columns it also
    declares -- `idx_worker_documents_verified ON worker_documents (verified)` --
    so re-applying it to a database that has the table but not that column dies
    with `column "verified" does not exist` *before* the ALTER that adds it. That
    aborted init_db() on precisely the older databases it exists to repair, so the
    column upgrades have to run before the script.

    This builds that state by creating the current schema and then dropping every
    column in _POSTGRES_COLUMN_UPGRADES, which is what a database from an earlier
    deploy looks like.
    """
    import pathlib

    import app.database as database_module

    with database_module.connection() as conn:
        conn.executescript((database_module.BASE_DIR / "schema.sql").read_text(encoding="utf-8"))
        for table, column, _decl in database_module._POSTGRES_COLUMN_UPGRADES:
            conn.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{column}"')

    def missing() -> set[tuple[str, str]]:
        with database_module.connection() as conn:
            absent = set()
            for table, column, _decl in database_module._POSTGRES_COLUMN_UPGRADES:
                present = {
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({table})")
                }
                if column not in present:
                    absent.add((table, column))
            return absent

    absent = missing()
    assert len(absent) == len(database_module._POSTGRES_COLUMN_UPGRADES), (
        f"the probe did not build an older database, only {len(absent)} columns missing"
    )

    database_module.init_db()

    still = missing()
    assert still == set(), f"init_db() did not converge the existing database: {sorted(still)}"
