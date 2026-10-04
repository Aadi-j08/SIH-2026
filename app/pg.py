"""
PostgreSQL behind the sqlite3 surface app/database.py expects.

psycopg 3 connections are wrapped so the rest of the codebase keeps working
unchanged: `?` placeholders, sqlite3.Row-style rows (name + positional access,
dict(row)), cursor.lastrowid, rowcount, executescript, PRAGMA table_info,
sqlite_master probes, INSERT OR IGNORE, BEGIN IMMEDIATE, sqlite3 date/arith
functions, and sqlite3.IntegrityError/OperationalError raised for PG failures
(so the exception handlers in app/main.py still fire).

Three behaviours are deliberately *not* left to psycopg's defaults, because the
defaults would silently differ from SQLite:

  - Transactions. The raw connection runs autocommit, and the wrapper opens one
    lazily on the first statement that SQLite would have wrapped (INSERT,
    UPDATE, DELETE, REPLACE), so `database.connection()` keeps its
    all-or-nothing meaning. Otherwise a signup that fails on its second INSERT
    would leave the first row committed.
  - BEGIN IMMEDIATE. Plain BEGIN is deferred in PostgreSQL and takes no lock, so
    the read-then-write blocks in booking_flow_db would no longer be
    serialised. It is rewritten to BEGIN plus a transaction-scoped advisory
    lock, which is the same single-writer guarantee SQLite gives.
  - lastrowid. `lastval()` is session-scoped and table-agnostic, so on a pooled
    connection it happily returns another table's id from an earlier request.
    The generated id is read from `RETURNING id` instead.

Anything not listed as translated is checked against a deny-list and raises,
rather than being handed to PostgreSQL to fail confusingly at query time.

Not translated:
  - INSERT OR REPLACE -- only scripts/seed_demo_data.py's SQLite branch uses it.
  - SQLite CREATE TRIGGER ... RAISE(ABORT ...) -- only the SQLite migration
    chain creates those; schema.sql already carries the CHECK constraints they
    emulate.

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


# The booking flow serialises all of its writes behind one lock, so the
# PostgreSQL equivalent has to be a single lock too rather than per-table ones.
# Any constant works as long as it is consistent; this value is arbitrary.
_BOOKING_FLOW_LOCK_KEY = 0x53494832_3032_3601  # "SIH2026" + 1


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


# ── statement classification ─────────────────────────────────────────────────

_TABLE_INFO = re.compile(
    r"^\s*PRAGMA\s+table_info\(\s*"
    r"(?:'([^']*)'|\"([^\"]*)\"|([A-Za-z_]\w*))"
    r"\s*\)\s*;?\s*$",
    re.I,
)

# SQLite connection tuning and integrity pragmas have no PostgreSQL equivalent.
# Answered with a trivial result so callers that ignore the cursor, and callers
# that iterate it, both behave.
_NOOP_PRAGMA = re.compile(
    r"^\s*PRAGMA\s+(foreign_keys|foreign_key_check|busy_timeout|journal_mode"
    r"|synchronous|user_version|integrity_check)\b",
    re.I,
)

_ANY_PRAGMA = re.compile(r"^\s*PRAGMA\b", re.I)

_INSERT_OR_IGNORE = re.compile(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO\b", re.I)
_BEGIN_IMMEDIATE = re.compile(r"^\s*BEGIN\s+IMMEDIATE\b", re.I)
_RETURNING = re.compile(r"\bRETURNING\b", re.I)
_INSERT_INTO = re.compile(
    r"^\s*INSERT\s+(?:OR\s+\w+\s+)?INTO\s+([A-Za-z_]\w*)", re.I
)

# Statements SQLite would wrap in an implicit transaction (isolation_level=""),
# and statements that manage transactions themselves.
_IMPLICIT_TXN = re.compile(r"^\s*(?:INSERT|UPDATE|DELETE|REPLACE)\b", re.I)
_TRANSACTION_CONTROL = re.compile(r"^\s*(BEGIN|COMMIT|ROLLBACK|END)\b", re.I)

# `INTEGER PRIMARY KEY AUTOINCREMENT` is SQLite-only. SERIAL is the equivalent.
_AUTOINCREMENT_PK = re.compile(
    r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", re.I
)

# sqlite_master becomes a subquery so every shape the app uses keeps working,
# including "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?".
# relkind 'r' is an ordinary table; 'v' covers a view if one is ever added.
_SQLITE_MASTER_SUBQUERY = (
    "(SELECT c.relname AS name, 'table' AS type FROM pg_class c "
    "JOIN pg_namespace n ON n.oid = c.relnamespace "
    "WHERE c.relkind IN ('r', 'v') AND n.nspname = current_schema())"
)

# ── sqlite scalar date / arithmetic functions ────────────────────────────────
#
# Only the forms this codebase actually issues, found by grepping app/ for each.
# Anything else in this family is caught by the deny-list.

# datetime('now', ?) -> NOW() plus a PostgreSQL interval. SQLite's modifier
# ('-24 hours', '+330 minutes') is interval syntax, so it casts directly.
_DATETIME_NOW_MOD = re.compile(
    r"\bdatetime\(\s*'now'\s*,\s*(\?|%s)\s*\)", re.I
)
# datetime(col) is SQLite's "normalise this column" no-op. The column is
# already a real timestamp on PostgreSQL.
_DATETIME_COLUMN = re.compile(r"\bdatetime\(\s*([A-Za-z_]\w*)\s*\)", re.I)
# DATE(col, 'modifier') -> shift by the interval, then truncate to a date.
_DATE_WITH_MODIFIER = re.compile(
    r"\bDATE\(\s*([A-Za-z_]\w*)\s*,\s*'([^']+)'\s*\)", re.I
)
# Two-argument MAX() is SQLite's scalar max; PostgreSQL spells that GREATEST.
_MAX_TWO_ARGS = re.compile(r"\bMAX\s*\(\s*([^()]*?,[^()]*?)\s*\)", re.I)

# SQLite constructs with no PostgreSQL spelling. Hitting one means a call site
# was not found when this module was written, so it is raised loudly here
# rather than surfacing as an opaque 500 on that endpoint.
_DENIED = (
    (re.compile(r"\bstrftime\s*\(", re.I),
     "strftime()"),
    (re.compile(r"\bjulianday\s*\(", re.I),
     "julianday()"),
    (re.compile(r"\bgroup_concat\s*\(", re.I),
     "group_concat()"),
    (re.compile(r"\bIFNULL\s*\(", re.I),
     "IFNULL()"),
    (re.compile(r"\bIIF\s*\(", re.I),
     "IIF()"),
    (re.compile(r"\blast_insert_rowid\s*\(", re.I),
     "last_insert_rowid()"),
    (re.compile(r"\bWITHOUT\s+ROWID\b", re.I),
     "WITHOUT ROWID"),
    (re.compile(r"^\s*ATTACH\b", re.I),
     "ATTACH"),
    (re.compile(r"^\s*VACUUM\b", re.I),
     "VACUUM"),
    (re.compile(r"\bRAISE\s*\(", re.I),
     "RAISE()"),
    (re.compile(r"\bGLOB\b", re.I),
     "GLOB"),
    (re.compile(r"\bsqlite_sequence\b", re.I),
     "sqlite_sequence"),
    (re.compile(r"^\s*INSERT\s+OR\s+(?!IGNORE\b)\w+", re.I),
     "INSERT OR <verb> other than INSERT OR IGNORE"),
)


def _unsupported(sql: str) -> str | None:
    """The first SQLite-only construct in `sql`, if any."""
    if _ANY_PRAGMA.match(sql) and not (
        _TABLE_INFO.match(sql) or _NOOP_PRAGMA.match(sql)
    ):
        return "an unhandled PRAGMA"
    for pattern, label in _DENIED:
        if pattern.search(sql):
            return label
    return None


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

    unsupported = _unsupported(text)
    if unsupported:
        raise NotImplementedError(
            f"{unsupported} has no PostgreSQL equivalent and is not translated by "
            f"app.pg. Rewrite this statement portably: {text[:200]}"
        )

    text = text.replace("sqlite_master", _SQLITE_MASTER_SUBQUERY)
    text = _BEGIN_IMMEDIATE.sub("BEGIN", text)
    text = _AUTOINCREMENT_PK.sub("SERIAL PRIMARY KEY", text)

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

    # SQLite scalar date/arith functions, before placeholder substitution so the
    # rewrites can match the `?` markers.
    text = _DATETIME_NOW_MOD.sub(r"(NOW() + CAST(\1 AS INTERVAL))", text)
    text = _DATETIME_COLUMN.sub(r"\1", text)
    text = _DATE_WITH_MODIFIER.sub(r"((\1 + CAST('\2' AS INTERVAL))::date)", text)
    text = _MAX_TWO_ARGS.sub(r"GREATEST(\1)", text)

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

        # BEGIN IMMEDIATE takes SQLite's write lock before any read. Plain
        # BEGIN is deferred in PostgreSQL, so the advisory lock is what
        # preserves the read-then-write serialisation callers rely on.
        if _BEGIN_IMMEDIATE.match(sql):
            self._conn._begin_immediate()
            return self

        if (
            self._conn is not None
            and _IMPLICIT_TXN.match(sql)
            and not self._conn._in_txn
        ):
            self._conn._begin_implicit()

        statement, returning_id = self._add_returning_id(sql, statement)

        try:
            self._cur.execute(statement, params or None)
        except Exception as exc:  # noqa: BLE001 - re-raised as sqlite3 types
            raise _wrap(exc) from exc

        self._rowcount = None
        if self._conn is not None and _TRANSACTION_CONTROL.match(sql):
            self._conn._in_txn = sql.strip().split()[0].upper() == "BEGIN"

        if _is_insert(sql):
            self.lastrowid = self._read_returned_id() if returning_id else None
        else:
            self.lastrowid = None
        return self

    def _add_returning_id(self, sql: str, statement: str) -> tuple[str, bool]:
        """Append RETURNING id so lastrowid needs no second round trip.

        Only for tables that actually have an `id` column: sessions,
        schema_migrations and standard_rates do not, and appending it there
        would be a syntax error at runtime.
        """
        if self._conn is None or not _is_insert(sql) or _RETURNING.search(sql):
            return statement, False
        target = _INSERT_INTO.match(sql)
        if not target:
            return statement, False
        if not self._conn._has_id_column(target.group(1)):
            return statement, False
        return f"{statement} RETURNING id", True

    def _read_returned_id(self):
        """Consume the RETURNING id row. None means no row was inserted.

        With ON CONFLICT DO NOTHING a conflict skips the row, so there is no new
        id; reporting a stale one from earlier on this connection would be
        worse than reporting none.
        """
        row = self._cur.fetchone()
        if not row:
            return None
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return None

    def executemany(self, sql: str, seq_of_params) -> "Cursor":
        # No RETURNING here: psycopg cannot return rows for executemany, and
        # nothing in the app reads lastrowid after one.
        statement = _translate(sql, has_params=True)
        try:
            self._cur.executemany(statement, seq_of_params)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        self._rowcount = None
        self.lastrowid = None
        return self

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

    __slots__ = ("_raw", "_in_txn", "_id_columns")

    def __init__(self, raw) -> None:
        self._raw = raw
        self._in_txn = False
        self._id_columns: dict[str, bool] = {}

    # -- transaction plumbing --------------------------------------------------

    def _begin_implicit(self) -> None:
        """Open the transaction SQLite's implicit DML handling would have opened."""
        try:
            self._raw.execute("BEGIN")
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        self._in_txn = True

    def _begin_immediate(self) -> None:
        """BEGIN IMMEDIATE: serialise writers before taking any read.

        The advisory lock is transaction-scoped, so COMMIT or ROLLBACK releases
        it. SQLite allows exactly one writer at a time, so one lock is the
        faithful equivalent rather than a per-table refinement.
        """
        try:
            self._raw.execute("BEGIN")
            self._raw.execute(
                "SELECT pg_advisory_xact_lock(%s)", (_BOOKING_FLOW_LOCK_KEY,)
            )
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        self._in_txn = True

    def _has_id_column(self, table: str) -> bool:
        """Whether `table` has an `id` column, cached per pooled connection."""
        cached = self._id_columns.get(table)
        if cached is None:
            row = self._raw.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'id' LIMIT 1",
                (table,),
            ).fetchone()
            cached = row is not None
            self._id_columns[table] = cached
        return cached

    # -- sqlite3 surface -------------------------------------------------------

    def cursor(self) -> Cursor:
        return Cursor(self._raw.cursor(), conn=self)

    def execute(self, sql: str, params=()) -> Cursor:
        return self.cursor().execute(sql, params)

    def executemany(self, sql: str, seq_of_params) -> Cursor:
        return self.cursor().executemany(sql, seq_of_params)

    def executescript(self, script: str) -> None:
        """Run a multi-statement DDL script atomically.

        psycopg sends a parameterless query through the simple protocol, so the
        whole script runs in one round trip and no statement splitting (and no
        risk of splitting inside a trigger body) is needed. No `%` escaping is
        applied here for the same reason.
        """
        owns = not self._in_txn
        if owns:
            self._begin_implicit()
        try:
            with self._raw.cursor() as cur:
                cur.execute(_translate(script, has_params=False))
            if owns:
                self.commit()
        except Exception as exc:  # noqa: BLE001
            if owns:
                self.rollback()
            raise _wrap(exc) from exc

    def commit(self) -> None:
        if not self._in_txn:
            return
        try:
            self._raw.commit()
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        finally:
            self._in_txn = False

    def rollback(self) -> None:
        if not self._in_txn:
            return
        try:
            self._raw.rollback()
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc
        finally:
            self._in_txn = False

    @property
    def in_transaction(self) -> bool:
        return self._in_txn

    @property
    def autocommit(self) -> bool:
        return not self._in_txn

    @autocommit.setter
    def autocommit(self, value: bool) -> None:
        # The raw connection is always autocommit; the wrapper decides. Setting
        # it True commits the open transaction, which is the sqlite3 meaning.
        if value:
            self.commit()

    def close(self) -> None:
        """No-op: the connection is pooled per thread and reused.

        A leaked transaction would poison the next request on this thread, so
        roll back rather than leaving one open.
        """
        if self._in_txn:
            try:
                self._raw.rollback()
            except Exception:  # noqa: BLE001
                pass
            self._in_txn = False

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# ── per-thread pool ──────────────────────────────────────────────────────────

_local = threading.local()


def _pooled() -> Connection:
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        # autocommit keeps psycopg from opening an implicit transaction behind
        # our back; the wrapper above opens one where SQLite would have.
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