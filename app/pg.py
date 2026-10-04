"""
PostgreSQL behind the sqlite3 surface app/database.py expects.

psycopg 3 connections are wrapped so the rest of the codebase keeps working
unchanged: `?` placeholders, sqlite3.Row-style rows (name + positional access,
dict(row)), cursor.lastrowid, rowcount, executescript, PRAGMA table_info,
sqlite_master probes, INSERT OR IGNORE, BEGIN IMMEDIATE/COMMIT issued as SQL,
and sqlite3.IntegrityError/OperationalError raised for PG failures (so the
exception handlers in app/main.py still fire).

Each statement is translated (_translate); everything else must already be
portable SQL. Deliberately NOT translated:
  - INSERT OR REPLACE — only scripts/seed_demo_data.py's SQLite branch uses it,
    unreachable when DATABASE_URL is a Postgres URL (it dispatches to its own
    seed_postgres() instead).
  - SQLite CREATE TRIGGER ... RAISE(ABORT ...) — skipped by the migrations in
    app/database.py; a fresh Postgres schema already has the CHECK constraints
    those triggers emulate, and assignments.booking_id is UNIQUE.

Connections are pooled per thread (Render -> Neon is cross-region; a fresh TLS
handshake per query block would dominate request latency). prepare_threshold is
disabled because Neon's -pooler endpoint (pgbouncer) dislikes server-side
prepared statements.
"""
from __future__ import annotations

import re
import sqlite3
import threading

import psycopg

from app.database import DATABASE_URL


# ── rows ─────────────────────────────────────────────────────────────────────

class Row:
    """sqlite3.Row look-alike: row["col"], row[0], dict(row), iteration."""

    __slots__ = ("_names", "_values", "_by_name")

    def __init__(self, names: tuple[str, ...], values: tuple) -> None:
        self._names = names
        self._values = values
        self._by_name = dict(zip(names, values))

    def keys(self):
        return list(self._names)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        try:
            return self._by_name[key]
        except KeyError:
            raise IndexError(f"No item matches {key!r}") from None

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __repr__(self) -> str:
        return f"<Row {self._by_name!r}>"


def _row_factory(cursor, values):
    return Row(tuple(d.name for d in cursor.description or ()), tuple(values))


# ── translation ──────────────────────────────────────────────────────────────

# Exposed as a subquery so every shape the app uses keeps working unchanged,
# including "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?".
# relkind 'r' is an ordinary table; 'v' covers a view if one is ever added.
_SQLITE_MASTER_SUBQUERY = (
    "(SELECT c.relname AS name, 'table' AS type FROM pg_class c "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE c.relkind IN ('r', 'v') AND n.nspname = current_schema())"
)

# SQLite accepts a bare or a quoted table name in table_info().
_TABLE_INFO = re.compile(
    r"^\s*PRAGMA\s+table_info\(\s*"
    r"(?:'([^']*)'|\"([^\"]*)\"|([A-Za-z_]\w*))"
    r"\s*\)\s*;?\s*$",
    re.I,
)

# SQLite connection tuning and integrity pragmas have no PostgreSQL equivalent.
# They are answered with a trivial result so callers that ignore the cursor,
# and callers that iterate it, both behave.
_NOOP_PRAGMA = re.compile(
    r"^\s*PRAGMA\s+(foreign_keys|foreign_key_check|busy_timeout|journal_mode"
    r"|synchronous|user_version|integrity_check)\b",
    re.I,
)

_INSERT_OR_IGNORE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", re.I)
_BEGIN_IMMEDIATE = re.compile(r"^\s*BEGIN\s+IMMEDIATE\b", re.I)
_RETURNING = re.compile(r"\bRETURNING\b", re.I)


def _translate(sql: str, *, has_params: bool) -> str:
    """Render one SQLite statement as PostgreSQL.

    `has_params` decides whether literal `%` is escaped. psycopg only runs the
    `%`-interpolation pass when parameters are supplied, so escaping when there
    are none would corrupt DDL that legitimately contains a percent sign.
    """
    text = sql.strip()

    table_info = _TABLE_INFO.match(text)
    if table_info:
        bare, single, double = table_info.groups()
        table = (bare or single or double or "").replace("'", "''")
        return (
            "SELECT column_name AS name FROM information_schema.columns "
            f"WHERE table_name = '{table}'"
        )

    if _NOOP_PRAGMA.match(text):
        return "SELECT 1"

    text = text.replace("sqlite_master", _SQLITE_MASTER_SUBQUERY)
    text = _BEGIN_IMMEDIATE.sub("BEGIN", text)

    if _INSERT_OR_IGNORE.match(text):
        text = _INSERT_OR_IGNORE.sub("INSERT INTO", text, count=1)
        text = text.rstrip().rstrip(";").rstrip()
        # ON CONFLICT must precede RETURNING, and a statement that already
        # carries its own RETURNING keeps it last.
        returning = _RETURNING.search(text)
        if returning:
            text = (
                text[: returning.start()]
                + " ON CONFLICT DO NOTHING "
                + text[returning.start() :]
            )
        else:
            text += " ON CONFLICT DO NOTHING"

    if not has_params:
        return text

    # `?` becomes psycopg's %s. Literal percent signs in the surrounding text
    # must be doubled or psycopg reads them as format specifiers. No statement
    # in this app embeds a literal % -- the LIKE patterns are all bound as
    # parameters (app/main.py) -- but doubling keeps that true by construction.
    parts = text.split("?")
    out: list[str] = []
    for index, part in enumerate(parts):
        out.append(part.replace("%", "%%"))
        if index < len(parts) - 1:
            out.append("%s")
    return "".join(out)


# ── error mapping ────────────────────────────────────────────────────────────

def _wrap(exc: BaseException) -> BaseException:
    """Re-raise psycopg failures as the sqlite3 exceptions callers catch."""
    if isinstance(exc, psycopg.errors.IntegrityError):
        return sqlite3.IntegrityError(str(exc))
    if isinstance(exc, psycopg.errors.OperationalError):
        return sqlite3.OperationalError(str(exc))
    if isinstance(exc, psycopg.errors.Error):
        return sqlite3.OperationalError(str(exc))
    return exc


# ── cursors and connections ──────────────────────────────────────────────────

class Cursor:
    """sqlite3.Cursor look-alike over a psycopg cursor."""

    __slots__ = ("_cur", "lastrowid", "_rowcount", "_conn")

    def __init__(self, cur, lastrowid=None, rowcount=None, conn=None) -> None:
        self._cur = cur
        self.lastrowid = lastrowid
        self._rowcount = rowcount
        self._conn = conn

    @property
    def rowcount(self) -> int:
        if self._rowcount is not None:
            return self._rowcount
        return self._cur.rowcount

    def execute(self, sql: str, params=()) -> "Cursor":
        statement = _translate(sql, has_params=bool(params))
        try:
            self._cur.execute(statement, params or None)
        except Exception as exc:  # noqa: BLE001 - re-raised as sqlite3 types
            raise _wrap(exc) from exc
        self._rowcount = None
        self.lastrowid = None
        if _is_insert(sql):
            self.lastrowid = self._fetch_lastval()
        return self

    def executemany(self, sql: str, seq_of_params) -> "Cursor":
        statement = _translate(sql, has_params=True)
        try:
            self._cur.executemany(statement, seq_of_params)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        self._rowcount = None
        self.lastrowid = None
        return self

    def _fetch_lastval(self):
        """psycopg has no cursor.lastrowid; read the sequence we just advanced.

        Only meaningful for tables with a SERIAL/IDENTITY column, which is every
        table the app inserts into and reads lastrowid from. Tables taking an
        explicit id (cooperative_federations, schema_migrations) do not use it.
        """
        try:
            self._cur.execute("SELECT lastval()")
            row = self._cur.fetchone()
            return int(row[0]) if row and row[0] is not None else None
        except Exception:  # noqa: BLE001 - lastrowid is best-effort
            return None

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size) if size is not None else self._cur.fetchmany()

    def close(self) -> None:
        self._cur.close()

    def __iter__(self):
        return iter(self._cur)


def _is_insert(sql: str) -> bool:
    return bool(re.match(r"^\s*INSERT\b", sql, re.I))


class Connection:
    """sqlite3.Connection look-alike over a pooled psycopg connection."""

    __slots__ = ("_raw",)

    def __init__(self, raw) -> None:
        self._raw = raw

    def cursor(self) -> Cursor:
        return Cursor(self._raw.cursor(), conn=self)

    def execute(self, sql: str, params=()) -> Cursor:
        return self.cursor().execute(sql, params)

    def executemany(self, sql: str, seq_of_params) -> Cursor:
        return self.cursor().executemany(sql, seq_of_params)

    def executescript(self, script: str) -> None:
        """Run a multi-statement DDL script.

        psycopg sends a parameterless query through the simple protocol, so the
        whole script runs in one round trip and no statement splitting (and no
        risk of splitting inside a trigger body) is needed. No `%` escaping is
        applied here for the same reason.
        """
        try:
            with self._raw.cursor() as cur:
                cur.execute(_translate(script, has_params=False))
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def commit(self) -> None:
        try:
            self._raw.commit()
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def rollback(self) -> None:
        try:
            self._raw.rollback()
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    @property
    def in_transaction(self) -> bool:
        status = self._raw.info.transaction_status
        return status != psycopg.pq.TransactionStatus.IDLE

    @property
    def autocommit(self) -> bool:
        return bool(self._raw.autocommit)

    @autocommit.setter
    def autocommit(self, value: bool) -> None:
        self._raw.autocommit = bool(value)

    def close(self) -> None:
        """No-op: the connection is pooled per thread and reused."""

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# ── per-thread pool ──────────────────────────────────────────────────────────

_local = threading.local()


def _pooled() -> Connection:
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        # autocommit keeps psycopg from opening an implicit transaction; the
        # app issues BEGIN/COMMIT itself, exactly as it does on SQLite.
        # prepare_threshold=None: Neon's pooled endpoint rejects prepared
        # statements.
        raw = psycopg.connect(DATABASE_URL, autocommit=True, prepare_threshold=None)
        raw.row_factory = _row_factory
        _local.conn = raw
        conn = raw
    return Connection(conn)


def _reset_thread_connection() -> None:
    """Drop this thread's pooled connection. Used by tests."""
    raw = getattr(_local, "conn", None)
    if raw is not None:
        try:
            raw.close()
        except Exception:  # noqa: BLE001
            pass
    _local.conn = None


def get_connection():
    """A Postgres-backed stand-in for database.get_connection()."""
    if not DATABASE_URL:
        raise RuntimeError(
            "app.pg.get_connection() called without DATABASE_URL set. "
            "This adapter only runs when a Postgres URL is configured."
        )
    return _pooled()