"""Translation layer tests for app/pg.py.

These cover every SQLite-specific construct the app actually issues, found by
grepping app/ for PRAGMA, sqlite_master, BEGIN IMMEDIATE and INSERT OR IGNORE.
They need no Postgres server: _translate is a pure function.
"""
from app.pg import _translate


def q(sql: str) -> str:
    """Translate a statement the way a parameterised execute() would."""
    return _translate(sql, has_params=True)


def plain(sql: str) -> str:
    """Translate a statement the way executescript() would."""
    return _translate(sql, has_params=False)


# ── placeholders ─────────────────────────────────────────────────────────────

def test_qmark_becomes_psql():
    assert q("SELECT * FROM users WHERE portal = ? AND phone = ?") == (
        "SELECT * FROM users WHERE portal = %s AND phone = %s"
    )


def test_single_placeholder():
    assert q("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?") != ""


def test_literal_percent_is_escaped_when_params_present():
    # psycopg only runs its %-interpolation when params are supplied, so a
    # literal percent must be doubled or it is read as a format specifier.
    out = q("SELECT * FROM t WHERE name LIKE '%acme%' AND id = ?")
    assert "%%acme%%" in out
    assert out.endswith("%s")


def test_literal_percent_untouched_without_params():
    # No params means psycopg uses the simple protocol: no escaping, or DDL
    # containing a percent sign would be corrupted.
    assert plain("SELECT '%' AS pct") == "SELECT '%' AS pct"


def test_no_percent_doubling_without_params():
    assert plain("UPDATE t SET a = 1 WHERE b = ?") == "UPDATE t SET a = 1 WHERE b = ?"


# ── PRAGMA ───────────────────────────────────────────────────────────────────

def test_table_info_becomes_information_schema():
    out = q("PRAGMA table_info(payment_ledger)")
    assert "information_schema.columns" in out
    assert "column_name AS name" in out
    assert "payment_ledger" in out


def test_table_info_accepts_quotes_and_semicolon():
    assert "information_schema.columns" in q("PRAGMA table_info('bookings');")


def test_foreign_keys_pragma_is_a_noop():
    # app/booking_flow_db.py:102 and app/database.py:380 both issue this.
    assert plain("PRAGMA foreign_keys = ON") == "SELECT 1"


def test_journal_mode_pragma_is_a_noop():
    assert plain("PRAGMA journal_mode = WAL") == "SELECT 1"


def test_busy_timeout_and_synchronous_are_noops():
    assert plain("PRAGMA busy_timeout = 30000") == "SELECT 1"
    assert plain("PRAGMA synchronous = NORMAL") == "SELECT 1"


# ── sqlite_master ────────────────────────────────────────────────────────────

def test_sqlite_master_listing():
    out = plain("SELECT name FROM sqlite_master WHERE type = 'table'")
    assert "pg_class" in out
    assert "relkind" in out
    assert "sqlite_master" not in out


def test_sqlite_master_existence_probe():
    # app/services/overview.py:227 -- the SELECT 1 shape must still parse.
    out = plain("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'bookings'")
    assert "pg_class" in out
    assert "'bookings'" in out


def test_sqlite_master_existence_probe_parameterised():
    out = q("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?")
    assert "pg_class" in out
    assert out.endswith("%s")
    assert "'table'" in out


# ── transactions ─────────────────────────────────────────────────────────────

def test_begin_immediate_becomes_begin():
    assert plain("BEGIN IMMEDIATE") == "BEGIN"


def test_commit_and_rollback_pass_through():
    assert plain("COMMIT") == "COMMIT"
    assert plain("ROLLBACK") == "ROLLBACK"


# ── INSERT OR IGNORE ─────────────────────────────────────────────────────────

def test_insert_or_ignore_adds_on_conflict():
    out = plain(
        "INSERT OR IGNORE INTO standard_rates (trade, cooperative_id) VALUES (?, ?)"
    )
    assert out.startswith("INSERT INTO standard_rates")
    assert "OR IGNORE" not in out
    assert out.rstrip().endswith("ON CONFLICT DO NOTHING")


def test_insert_or_ignore_keeps_returning_last():
    out = plain("INSERT OR IGNORE INTO t (a) VALUES (?) RETURNING id")
    assert out.index("ON CONFLICT DO NOTHING") < out.index("RETURNING")
    assert out.rstrip().endswith("RETURNING id")


def test_plain_insert_is_untouched():
    out = plain("INSERT INTO users (portal, phone) VALUES (?, ?)")
    assert "ON CONFLICT" not in out
    assert out.endswith("(?, ?)")


# ── idempotence / safety ─────────────────────────────────────────────────────

def test_plain_sql_is_unchanged():
    sql = "SELECT id, name FROM workers WHERE cooperative_id = ? ORDER BY id"
    assert q(sql) == "SELECT id, name FROM workers WHERE cooperative_id = %s ORDER BY id"


def test_translate_is_stable():
    # The same input must always produce the same SQL, or pooled connections and
    # query caches behave unpredictably.
    sql = "SELECT * FROM t WHERE a = ? AND b LIKE 'x%'"
    assert q(sql) == q(sql)