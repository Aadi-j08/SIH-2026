"""
DB access functions for workers and bookings.

Plain sqlite3 over app/database.py; every function opens its own short
connection and returns models from app/schemas.py. The booking flow
(app/services/booking_flow.py) manages its own transactions separately.
"""
from __future__ import annotations

import json
import sqlite3

from app.database import connection
from app.schemas import (
    AvailabilityWindow,
    Booking,
    BookingCreate,
    Worker,
    WorkerCreate,
    WorkerProfile,
)


# ── row <-> model ────────────────────────────────────────────────────────

def _worker_data(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["availability"] = json.loads(data.get("availability") or "[]")
    return data


def _worker(row: sqlite3.Row) -> Worker:
    return Worker.model_validate(_worker_data(row))


def _booking(row: sqlite3.Row) -> Booking:
    return Booking.model_validate(dict(row))


def _dump_windows(windows: list[AvailabilityWindow]) -> str:
    return json.dumps([w.model_dump(mode="json") for w in windows])


def _normalise_trade(trade: str) -> str:
    return trade.strip().lower()


# ── workers ──────────────────────────────────────────────────────────────

def create_worker(data: WorkerCreate, status: str = "active") -> Worker:
    """Council-registered workers are active at once; self sign-ups pass status="pending" and wait for approval."""
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO workers (name, phone, trade, latitude, longitude, rating, availability, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data.name.strip(), data.phone, _normalise_trade(data.trade), data.latitude, data.longitude,
             data.rating, _dump_windows(data.availability), status),
        )
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _worker(row)


def get_worker(worker_id: int) -> Worker | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
    return _worker(row) if row else None


def list_workers(trade: str | None = None) -> list[Worker]:
    with connection() as conn:
        if trade:
            rows = conn.execute("SELECT * FROM workers WHERE trade = ? ORDER BY id", (_normalise_trade(trade),))
        else:
            rows = conn.execute("SELECT * FROM workers ORDER BY id")
        return [_worker(row) for row in rows]


def worker_profiles(trade: str | None = None) -> list[WorkerProfile]:
    """Workers as the allocation engine wants them. Workers still awaiting council approval are left out."""
    return [WorkerProfile.model_validate(w.model_dump()) for w in list_workers(trade) if w.status == "active"]


def set_worker_status(worker_id: int, status: str) -> Worker | None:
    with connection() as conn:
        conn.execute("UPDATE workers SET status = ? WHERE id = ?", (status, worker_id))
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
    return _worker(row) if row else None


def set_worker_availability(
    worker_id: int, windows: list[AvailabilityWindow], replace: bool = True
) -> Worker | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
        if row is None:
            return None
        if not replace:
            existing = Worker.model_validate(_worker_data(row)).availability
            windows = existing + [w for w in windows if w not in existing]
        conn.execute("UPDATE workers SET availability = ? WHERE id = ?", (_dump_windows(windows), worker_id))
        row = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
    return _worker(row)


# ── bookings ─────────────────────────────────────────────────────────────

def create_booking(data: BookingCreate) -> Booking:
    with connection() as conn:
        cursor = conn.execute(
            "INSERT INTO bookings (customer_name, customer_phone, trade, latitude, longitude, address, scheduled_for) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data.customer_name.strip(), data.customer_phone, _normalise_trade(data.trade), data.latitude,
             data.longitude, data.address, data.scheduled_for.isoformat() if data.scheduled_for else None),
        )
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _booking(row)


def get_booking(booking_id: int) -> Booking | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    return _booking(row) if row else None


def list_bookings(status: str | None = None, trade: str | None = None) -> list[Booking]:
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if trade:
        clauses.append("trade = ?")
        params.append(_normalise_trade(trade))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connection() as conn:
        rows = conn.execute(f"SELECT * FROM bookings {where} ORDER BY id", params)
        return [_booking(row) for row in rows]


def demand_dates(trade: str | None = None) -> list[str]:
    """When each booking's demand falls: the requested slot, or when it was placed. Feeds the forecast."""
    with connection() as conn:
        if trade:
            rows = conn.execute(
                "SELECT COALESCE(scheduled_for, created_at) AS demand_at FROM bookings WHERE trade = ?",
                (_normalise_trade(trade),),
            )
        else:
            rows = conn.execute("SELECT COALESCE(scheduled_for, created_at) AS demand_at FROM bookings")
        return [row["demand_at"] for row in rows]
