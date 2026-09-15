"""
Settlement — the price of a finished job, agreed by both sides.

Nobody types a bill on their own. When the work is done the worker says how
long it took and what materials went in; the rate card turns that into a
standard amount and a fair band around it. The customer, who was there,
agrees, counters within the band, or asks the Sabha to decide. The moment
both sides agree, the booking completes and the existing ledger splits the
amount 85/10/5. Money is then paid customer → worker directly (cash or
UPI); the platform records the agreement, never the payment.

    worker   POST /bookings/{id}/settlement            propose  (hours, materials, note, amount within band)
    customer POST /bookings/{id}/settlement/respond    agree | counter | dispute
    worker   POST /bookings/{id}/settlement/respond    agree (to the counter) | dispute
    council  POST /bookings/{id}/settlement/resolve    fix the amount, close the dispute
    anyone party to it   GET /bookings/{id}/settlement
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app import rates
from app.auth import User
from app.booking_flow_db import booking_flow_connection, immediate_transaction
from app.services import booking_flow
from app.services.ledger import paise_to_rupees, rupees_to_paise

log = logging.getLogger("sahakarsetu.settlements")

Status = Literal["proposed", "countered", "agreed", "disputed"]
PaidVia = Literal["cash", "upi", "other"]


class SettlementError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# ── models ───────────────────────────────────────────────────────────────

class Propose(BaseModel):
    hours_worked: float = Field(gt=0, le=24, description="Time on the job, in hours (0.5 steps are fine)")
    materials_rupees: Decimal = Field(default=Decimal(0), ge=0, le=1_000_000, decimal_places=2)
    work_note: str | None = Field(default=None, max_length=300, description="What was done, for the customer and the record")
    amount_rupees: Decimal | None = Field(default=None, gt=0, le=10_000_000, decimal_places=2,
                                          description="Omit to propose the rate-card amount; else must sit inside the fair band")


class Respond(BaseModel):
    action: Literal["agree", "counter", "dispute"]
    amount_rupees: Decimal | None = Field(default=None, gt=0, le=10_000_000, decimal_places=2, description="For a counter")
    note: str | None = Field(default=None, max_length=300)
    paid_via: PaidVia | None = Field(default=None, description="How the customer paid the worker (recorded, never processed)")


class Resolve(BaseModel):
    amount_rupees: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)
    resolution: str = Field(min_length=1, max_length=1000)


class Settlement(BaseModel):
    id: int
    booking_id: int
    worker_id: int
    worker_name: str | None = None
    customer_name: str | None = None
    trade: str
    status: Status
    hours_worked: float
    materials_rupees: float
    work_note: str | None
    standard_rupees: float
    min_fair_rupees: float
    max_fair_rupees: float
    proposed_rupees: float
    counter_rupees: float | None
    customer_note: str | None
    agreed_rupees: float | None
    paid_via: PaidVia | None
    dispute_id: int | None
    created_at: str
    responded_at: str | None
    agreed_at: str | None
    waiting_on: Literal["customer", "worker", "council"] | None = Field(description="Whose move it is; None once agreed")
    explanation: str
    ledger: list[dict[str, Any]] = Field(default_factory=list, description="The 85/10/5 split once agreed")


# ── helpers ──────────────────────────────────────────────────────────────

_SELECT = """
    SELECT s.*, b.trade, b.customer_name, b.customer_user_id, b.status AS booking_status, w.name AS worker_name
    FROM settlements s
    JOIN bookings b ON b.id = s.booking_id
    JOIN workers w ON w.id = s.worker_id
"""


def _row(conn: sqlite3.Connection, booking_id: int) -> sqlite3.Row | None:
    return conn.execute(_SELECT + " WHERE s.booking_id = ?", (booking_id,)).fetchone()


def _model(conn: sqlite3.Connection, row: sqlite3.Row) -> Settlement:
    q = rates.quote(conn, row["trade"], row["hours_worked"], paise_to_rupees(row["materials_paise"]))
    status = row["status"]
    waiting = None if status == "agreed" else "customer" if status == "proposed" else "worker" if status == "countered" else "council"
    ledger = [
        {**dict(r), "amount_rupees": paise_to_rupees(r["amount_paise"])}
        for r in conn.execute("SELECT party, share_percent, amount_paise FROM payment_ledger WHERE booking_id = ? ORDER BY id", (row["booking_id"],))
    ] if status == "agreed" else []
    return Settlement(
        id=row["id"], booking_id=row["booking_id"], worker_id=row["worker_id"], worker_name=row["worker_name"],
        customer_name=row["customer_name"], trade=row["trade"], status=status, hours_worked=row["hours_worked"],
        materials_rupees=paise_to_rupees(row["materials_paise"]), work_note=row["work_note"],
        standard_rupees=paise_to_rupees(row["standard_paise"]), min_fair_rupees=q.min_fair_rupees, max_fair_rupees=q.max_fair_rupees,
        proposed_rupees=paise_to_rupees(row["proposed_paise"]),
        counter_rupees=paise_to_rupees(row["counter_paise"]) if row["counter_paise"] is not None else None,
        customer_note=row["customer_note"], agreed_rupees=paise_to_rupees(row["agreed_paise"]) if row["agreed_paise"] is not None else None,
        paid_via=row["paid_via"], dispute_id=row["dispute_id"], created_at=row["created_at"], responded_at=row["responded_at"],
        agreed_at=row["agreed_at"], waiting_on=waiting, explanation=q.explanation, ledger=ledger,
    )


def _assigned_worker(conn: sqlite3.Connection, booking_id: int) -> tuple[sqlite3.Row, int]:
    booking = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    if booking is None:
        raise SettlementError(404, f"Booking {booking_id} not found")
    assignment = conn.execute("SELECT worker_id FROM assignments WHERE booking_id = ? ORDER BY id DESC LIMIT 1", (booking_id,)).fetchone()
    if booking["status"] != "assigned" or assignment is None:
        raise SettlementError(409, f"Booking {booking_id} is '{booking['status']}'; a price is agreed on an assigned job")
    return booking, assignment["worker_id"]


def _ensure_party(user: User, row: sqlite3.Row) -> None:
    if user.is_council:
        return
    if user.access_role == "customer" and row["customer_user_id"] == user.id:
        return
    if user.access_role == "worker" and user.worker_id == row["worker_id"]:
        return
    raise SettlementError(403, "This settlement is between the customer and the worker of the booking")


def _in_band(amount_paise: int, standard_paise: int, band_percent: int) -> bool:
    slack = standard_paise * band_percent // 100
    return standard_paise - slack <= amount_paise <= standard_paise + slack


def _open_dispute(conn: sqlite3.Connection, booking_id: int, user: User, amount_paise: int, note: str | None) -> int:
    existing = conn.execute("SELECT id FROM disputes WHERE booking_id = ? AND status = 'open'", (booking_id,)).fetchone()
    if existing is not None:
        return existing["id"]
    cursor = conn.execute(
        "INSERT INTO disputes (booking_id, kind, raised_by, raised_by_user_id, amount_paise, description) VALUES (?, 'payment', ?, ?, ?, ?)",
        (booking_id, user.access_role, user.id, amount_paise, (note or "").strip() or "Could not agree the price of the job; asked the Sabha to decide."),
    )
    return int(cursor.lastrowid)


def _complete(conn: sqlite3.Connection, booking_id: int, amount_paise: int) -> None:
    """Close the booking through the existing flow so the ledger and worker stats stay exactly as before."""
    try:
        booking_flow.complete_booking(conn, booking_id, Decimal(amount_paise) / 100)
    except booking_flow.BookingFlowError as exc:
        raise SettlementError(exc.status_code, str(exc)) from exc


# ── operations ───────────────────────────────────────────────────────────

def get(user: User, booking_id: int) -> Settlement | None:
    with booking_flow_connection() as conn:
        row = _row(conn, booking_id)
        if row is None:
            booking = conn.execute("SELECT id FROM bookings WHERE id = ?", (booking_id,)).fetchone()
            if booking is None:
                raise SettlementError(404, f"Booking {booking_id} not found")
            return None
        _ensure_party(user, row)
        return _model(conn, row)


def propose(user: User, booking_id: int, data: Propose) -> Settlement:
    """The worker (or council on their behalf) says what the job took; the card prices it."""
    with booking_flow_connection() as conn:
        with immediate_transaction(conn):
            booking, worker_id = _assigned_worker(conn, booking_id)
            if not user.is_council and user.worker_id != worker_id:
                raise SettlementError(403, "This job is assigned to another worker")
            if _row(conn, booking_id) is not None:
                raise SettlementError(409, f"Booking {booking_id} already has a price on the table")
            q = rates.quote(conn, booking["trade"], data.hours_worked, float(data.materials_rupees))
            standard_paise = rupees_to_paise(Decimal(str(q.standard_rupees)))
            proposed_paise = rupees_to_paise(data.amount_rupees) if data.amount_rupees is not None else standard_paise
            if not _in_band(proposed_paise, standard_paise, q.band_percent):
                raise SettlementError(
                    422, f"₹{proposed_paise / 100:.0f} is outside the fair band (₹{q.min_fair_rupees:.0f}–₹{q.max_fair_rupees:.0f}) "
                         f"the community set for this job. Propose within it, or ask the Sabha."
                )
            conn.execute(
                "INSERT INTO settlements (booking_id, worker_id, hours_worked, materials_paise, work_note, standard_paise, proposed_paise) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (booking_id, worker_id, data.hours_worked, rupees_to_paise(data.materials_rupees), (data.work_note or "").strip() or None,
                 standard_paise, proposed_paise),
            )
        log.info("settlement proposed on booking %s: %s paise by %s #%s", booking_id, proposed_paise, user.access_role, user.id)
        return _model(conn, _row(conn, booking_id))


def respond(user: User, booking_id: int, data: Respond) -> Settlement:
    """The customer answers a proposal; the worker answers a counter. Agreement completes the job."""
    with booking_flow_connection() as conn:
        agreed_paise: int | None = None
        with immediate_transaction(conn):
            row = _row(conn, booking_id)
            if row is None:
                raise SettlementError(404, f"Booking {booking_id} has no price on the table yet")
            _ensure_party(user, row)
            status = row["status"]
            if status in ("agreed", "disputed"):
                raise SettlementError(409, f"This settlement is already {status}")
            side = "council" if user.is_council else user.access_role
            on_table = row["counter_paise"] if status == "countered" else row["proposed_paise"]
            expected = "customer" if status == "proposed" else "worker"
            if side != "council" and side != expected:
                raise SettlementError(409, f"It is the {expected}'s turn to reply")

            if data.action == "agree":
                agreed_paise = on_table
                conn.execute(
                    "UPDATE settlements SET status = 'agreed', agreed_paise = ?, paid_via = COALESCE(?, paid_via), "
                    "customer_note = COALESCE(?, customer_note), responded_at = CURRENT_TIMESTAMP, agreed_at = CURRENT_TIMESTAMP WHERE booking_id = ?",
                    (agreed_paise, data.paid_via, (data.note or "").strip() or None, booking_id),
                )
            elif data.action == "counter":
                if side != "customer" and side != "council":
                    raise SettlementError(409, "Only the customer counters; the worker agrees to the counter or asks the Sabha")
                if data.amount_rupees is None:
                    raise SettlementError(422, "A counter needs an amount")
                counter_paise = rupees_to_paise(data.amount_rupees)
                q = rates.quote(conn, row["trade"], row["hours_worked"], paise_to_rupees(row["materials_paise"]))
                if not _in_band(counter_paise, row["standard_paise"], q.band_percent):
                    raise SettlementError(
                        422, f"₹{counter_paise / 100:.0f} is outside the fair band (₹{q.min_fair_rupees:.0f}–₹{q.max_fair_rupees:.0f}). "
                             f"Offer within it, or ask the Sabha to decide."
                    )
                if status == "countered":
                    raise SettlementError(409, "A counter is already on the table; wait for the worker's reply")
                conn.execute(
                    "UPDATE settlements SET status = 'countered', counter_paise = ?, customer_note = ?, responded_at = CURRENT_TIMESTAMP WHERE booking_id = ?",
                    (counter_paise, (data.note or "").strip() or None, booking_id),
                )
            else:  # dispute → the Sabha decides
                dispute_id = _open_dispute(conn, booking_id, user, on_table, data.note)
                conn.execute(
                    "UPDATE settlements SET status = 'disputed', dispute_id = ?, customer_note = COALESCE(?, customer_note), responded_at = CURRENT_TIMESTAMP WHERE booking_id = ?",
                    (dispute_id, (data.note or "").strip() or None, booking_id),
                )
        if agreed_paise is not None:
            _complete(conn, booking_id, agreed_paise)
            log.info("settlement agreed on booking %s at %s paise (%s)", booking_id, agreed_paise, side)
        return _model(conn, _row(conn, booking_id))


def resolve(user: User, booking_id: int, data: Resolve) -> Settlement:
    """The council fixes the amount of a disputed settlement and closes the dispute with a note."""
    amount_paise = rupees_to_paise(data.amount_rupees)
    with booking_flow_connection() as conn:
        with immediate_transaction(conn):
            row = _row(conn, booking_id)
            if row is None:
                raise SettlementError(404, f"Booking {booking_id} has no settlement")
            if row["status"] == "agreed":
                raise SettlementError(409, "This settlement is already agreed")
            conn.execute(
                "UPDATE settlements SET status = 'agreed', agreed_paise = ?, responded_at = CURRENT_TIMESTAMP, agreed_at = CURRENT_TIMESTAMP WHERE booking_id = ?",
                (amount_paise, booking_id),
            )
            if row["dispute_id"] is not None:
                conn.execute(
                    "UPDATE disputes SET status = 'resolved', resolution = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'open'",
                    (data.resolution.strip(), row["dispute_id"]),
                )
        _complete(conn, booking_id, amount_paise)
        log.info("settlement on booking %s resolved by council #%s at %s paise", booking_id, user.id, amount_paise)
        return _model(conn, _row(conn, booking_id))


def list_all(status: str | None = None, limit: int = 100) -> list[Settlement]:
    where = ""
    params: tuple[Any, ...] = ()
    if status == "open":
        where = " WHERE s.status IN ('proposed', 'countered', 'disputed')"
    elif status:
        where, params = " WHERE s.status = ?", (status,)
    with booking_flow_connection() as conn:
        rows = conn.execute(
            _SELECT + where + " ORDER BY (s.status = 'agreed'), COALESCE(s.responded_at, s.created_at) DESC, s.id DESC LIMIT ?", (*params, limit)
        ).fetchall()
        return [_model(conn, r) for r in rows]


def open_settlements(conn: sqlite3.Connection, older_than_hours: float | None = None) -> list[dict[str, Any]]:
    """Settlements still waiting on someone (for the Sabha's attention list)."""
    rows = conn.execute(
        _SELECT + " WHERE s.status IN ('proposed', 'countered') ORDER BY s.created_at"
    ).fetchall()
    if older_than_hours is None:
        return [dict(r) for r in rows]
    cutoff = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(hours=older_than_hours)
    return [dict(r) for r in rows if dt.datetime.fromisoformat(r["responded_at"] or r["created_at"]) <= cutoff]
