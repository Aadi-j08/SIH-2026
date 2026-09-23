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


class Cursor:
    """sqlite3.Cursor look-alike over a psycopg cursor."""

    __slots__ = ("_cur", "lastrowid", "_rowcount")

    def __init__(self, cur, lastrowid=None, rowcount=None) -> None:
        self._cur = cur
        self.lastrowid = lastrowid
        self._rowcount = rowcount

    @property
    def rowcount(self) -> int:
        if self._rowcount is not None:
            return self._rowcount
        return self._cur.rowcount

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)
