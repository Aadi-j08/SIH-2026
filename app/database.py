"""
SQLite setup for SahakarSetu.

One file-based database, no ORM. The path comes from the SAHAKARSETU_DB
environment variable and defaults to sahakarsetu.db in the project root.
Tests point DB_PATH at a temporary file, so every function here reads
DB_PATH at call time instead of capturing it at import.
"""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("SAHAKARSETU_DB", BASE_DIR / "sahakarsetu.db"))

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
    jobs_this_week  INTEGER NOT NULL DEFAULT 0,
    rating          REAL,                          -- 1..5, NULL until first rating
    availability    TEXT    NOT NULL DEFAULT '[]', -- JSON list of AvailabilityWindow
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
    status          TEXT    NOT NULL DEFAULT 'pending',
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id      INTEGER NOT NULL REFERENCES bookings(id),
    worker_id       INTEGER NOT NULL REFERENCES workers(id),
    score           REAL,                          -- allocation engine score, 0..1
    created_at      TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workers_trade        ON workers (trade);
CREATE INDEX IF NOT EXISTS idx_bookings_status      ON bookings (status);
CREATE INDEX IF NOT EXISTS idx_bookings_trade       ON bookings (trade);
CREATE INDEX IF NOT EXISTS idx_assignments_booking  ON assignments (booking_id);
CREATE INDEX IF NOT EXISTS idx_assignments_worker   ON assignments (worker_id);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection with row access by column name and foreign keys on."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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


def init_db() -> None:
    """Create the core tables if they do not exist. Safe to call repeatedly."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.executescript(SCHEMA)
