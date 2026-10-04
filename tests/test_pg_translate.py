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

# ── SQLite scalar date / arithmetic functions ────────────────────────────────
#
# Each of these was found by grepping app/ for the construct; the four below are
# every occurrence in the codebase. They would otherwise reach PostgreSQL
# verbatim and 500 the endpoint that issued them.

def test_datetime_now_with_modifier_becomes_interval_arithmetic():
    # app/services/overview.py:373
    out = q("AND COALESCE(responded_at, created_at) <= datetime('now', ?)")
    assert "NOW() + CAST(%s AS INTERVAL)" in out
    assert "datetime(" not in out


def test_datetime_on_a_column_is_identity():
    # app/services/overview.py:521,524,528 -- normalising a stored timestamp.
    assert q("AND datetime(created_at) >= ?") == "AND created_at >= %s"
    assert q("SELECT COUNT(*) FROM bookings WHERE datetime(started_at) >= ?") == (
        "SELECT COUNT(*) FROM bookings WHERE started_at >= %s"
    )


def test_date_with_modifier_shifts_then_truncates():
    # app/kaam.py:162,163,170 and app/services/booking_flow.py:396
    out = q("COUNT(DISTINCT DATE(created_at, '+330 minutes')) AS engagement_days")
    assert "(created_at + CAST('+330 minutes' AS INTERVAL))::date" in out
    assert "DATE(" not in out


def test_two_arg_max_becomes_greatest():
    # app/kaam.py:375 -- SQLite's scalar max; GREATEST is the PostgreSQL spelling.
    out = q("UPDATE workers SET jobs_this_week = MAX(0, jobs_this_week - 1) WHERE id = ?")
    assert "GREATEST(0, jobs_this_week - 1)" in out
    assert "MAX(" not in out


def test_one_arg_max_aggregate_is_untouched():
    # MAX(a) is an aggregate in both engines and must not become GREATEST.
    assert "MAX(amount_paise)" in plain("SELECT MAX(amount_paise) FROM payment_ledger")


def test_max_aggregate_with_a_nested_comma_is_untouched():
    # COALESCE(MAX(x), 0) has a comma in COALESCE, not in MAX.
    sql = "SELECT COALESCE(MAX(amount_paise), 0) FROM payment_ledger"
    assert plain(sql) == sql


# ── AUTOINCREMENT ────────────────────────────────────────────────────────────

def test_autoincrement_primary_key_becomes_serial():
    # app/services/assistant.py:44 declares assistant_audit with this form.
    out = plain(
        "CREATE TABLE IF NOT EXISTS assistant_audit ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL)"
    )
    assert "AUTOINCREMENT" not in out
    assert "id SERIAL PRIMARY KEY" in out


def test_schema_constant_contains_no_sqlite_only_syntax():
    """Regression guard for the boot crash: SCHEMA must never reach PostgreSQL."""
    from app import database

    for statement in database.SCHEMA.split(";"):
        statement = statement.strip()
        if not statement:
            continue
        # Would raise NotImplementedError if SQLite-only syntax were present.
        _translate(statement, has_params=False)


def test_schema_sql_itself_translates_cleanly():
    from app import database

    script = (database.BASE_DIR / "schema.sql").read_text(encoding="utf-8")
    _translate(script, has_params=False)


# ── deny-list ────────────────────────────────────────────────────────────────

def test_denied_constructs_raise_with_a_useful_message():
    import pytest

    for sql, needle in [
        ("SELECT strftime('%Y', created_at) FROM bookings", "strftime()"),
        ("SELECT julianday(created_at) FROM bookings", "julianday()"),
        ("SELECT group_concat(name) FROM workers", "group_concat()"),
        ("SELECT IFNULL(a, b) FROM bookings", "IFNULL()"),
        ("SELECT IIF(a, 1, 2) FROM bookings", "IIF()"),
        ("CREATE TABLE t (id INTEGER PRIMARY KEY) WITHOUT ROWID", "WITHOUT ROWID"),
        ("ATTACH DATABASE 'x.db' AS x", "ATTACH"),
        ("VACUUM", "VACUUM"),
        ("CREATE TRIGGER t BEFORE INSERT ON x BEGIN SELECT RAISE(ABORT, 'no'); END", "RAISE()"),
        ("SELECT * FROM t WHERE name GLOB 'a*'", "GLOB"),
        ("SELECT * FROM sqlite_sequence", "sqlite_sequence"),
        ("INSERT OR REPLACE INTO workers (id) VALUES (1)", "INSERT OR"),
    ]:
        with pytest.raises(NotImplementedError, match=needle):
            _translate(sql, has_params=False)


def test_unhandled_pragma_is_denied():
    import pytest

    with pytest.raises(NotImplementedError, match="unhandled PRAGMA"):
        _translate("PRAGMA incremental_vacuum", has_params=False)


def test_handled_pragmas_are_not_denied():
    assert plain("PRAGMA table_info(workers)") != ""
    assert plain("PRAGMA foreign_keys = ON") == "SELECT 1"


def test_deny_list_does_not_false_positive_on_translated_forms():
    # The rewrites above must not trip the checks.
    _translate("SELECT datetime('now', ?)", has_params=True)
    _translate("SELECT MAX(0, x) FROM t", has_params=True)
    _translate("SELECT id FROM sqlite_master WHERE type = 'table'", has_params=False)
    _translate("INSERT OR IGNORE INTO t (a) VALUES (?)", has_params=True)
