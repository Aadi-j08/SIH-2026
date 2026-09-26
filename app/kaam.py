"""
Kaam — what a worker sees and does in their own portal.

  summary          the numbers on the Kaam home page (their share, not the council's dashboard)
  jobs             every job that touched this worker: assigned, completed (with the 85/10/5 split
                   and the rating), passed on
  availability     structured edits to the windows the voice parser wrote (remove, mark busy, add)
  accept/decline   the worker's reply to an assignment; a decline sends the booking straight to
                   the next-best worker through the existing assign step, excluding whoever passed
  approval         new Kaam sign-ups wait as 'pending' until the council approves them

The booking flow's own transactions (app/services/booking_flow.py) are reused
where they exist; the few extra writes live here.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from typing import Any, Literal

from pydantic import BaseModel, Field

from app import repository, tenancy
from app.booking_flow_db import booking_flow_connection, immediate_transaction
from app.database import connection
from app.schemas import AvailabilityWindow, Worker
from app.services import booking_flow
from app.services.booking_flow import ELIGIBILITY_DAYS, BookingFlowError, InvalidBookingState, NoEligibleWorker
from app.services.ledger import SPLIT_PERCENT, paise_to_rupees

DeclineReason = Literal["unwell", "too_far", "already_booked", "not_my_job", "other"]
DECLINE_LABELS: dict[str, str] = {
    "unwell": "not well", "too_far": "too far", "already_booked": "already booked",
    "not_my_job": "not their kind of job", "other": "other reason",
}
_IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


class KaamError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# ── models ───────────────────────────────────────────────────────────────

class WorkerSummary(BaseModel):
    worker_id: int
    status: str
    jobs_this_week: int
    completed_jobs: int
    share_rupees: float = Field(description="Worker's 85% share, all time")
    share_this_month_rupees: float
    billed_this_month_rupees: float
    rating: float | None
    rating_count: int
    engagement_days: int
    days_to_benefits: int
    eligibility_days: int = ELIGIBILITY_DAYS
    free_hours_this_week: float
    awaiting_reply: int = Field(description="Assigned jobs the worker has not accepted yet")
    split_percent: dict[str, int] = Field(default_factory=lambda: dict(SPLIT_PERCENT))


class WorkerJob(BaseModel):
    booking_id: int
    customer_name: str
    customer_phone: str | None
    trade: str
    address: str | None
    latitude: float
    longitude: float
    scheduled_for: str | None
    outcome: Literal["assigned", "accepted", "in_progress", "completed", "declined"]
    assigned_at: str | None = None
    accepted_at: str | None = None
    started_at: str | None = None
    start_selfie_url: str | None = None
    end_photo_url: str | None = None
    completed_at: str | None = None
    explanation: str | None = None
    billed_rupees: float | None = None
    share_rupees: float | None = None
    rating: int | None = None
    rating_comment: str | None = None
    decline_reason: str | None = None
    declined_at: str | None = None
    settlement: dict[str, Any] | None = Field(default=None, description="The price on the table (status, amounts, whose turn) once the worker has proposed one")


class StartWorkRequest(BaseModel):
    start_selfie_url: str | None = Field(default=None, description="Base64 or URL of arrival selfie")


class ProofOfWorkRequest(BaseModel):
    start_selfie_url: str | None = None
    end_photo_url: str | None = Field(default=None, description="Base64 or URL of completed work photo")


class AvailabilityUpdate(BaseModel):
    windows: list[AvailabilityWindow]


class WindowPatch(BaseModel):
    start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    available: bool | None = None


class DeclineRequest(BaseModel):
    reason: DeclineReason
    note: str | None = Field(default=None, max_length=200)
    mark_busy_today: bool = Field(default=False, description="Also add a busy window for the rest of today")


class ReplyResult(BaseModel):
    booking_id: int
    status: str
    reassigned_to: str | None = Field(default=None, description="After a decline: the next worker's name, or None if it stayed pending")


# ── summary ──────────────────────────────────────────────────────────────

def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def free_hours(windows: list[AvailabilityWindow], start: dt.date, days: int = 7) -> float:
    """Hours the worker is free over the next `days` days: free windows minus busy ones, per day."""
    total = 0
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        free = [False] * 1440
        for busy in (False, True):    # free windows first, then busy ones override
            for w in windows:
                if w.available is busy:
                    continue
                applies = (w.date == day) if w.date else (w.weekday == day.weekday()) if w.weekday is not None else True
                if not applies:
                    continue
                lo, hi = _minutes(w.start), _minutes(w.end)
                for minute in range(max(0, lo), min(1440, hi + (1 if w.end == "23:59" else 0))):
                    free[minute] = not busy
        total += sum(free)
    return round(total / 60, 1)


def summary(worker_id: int) -> WorkerSummary:
    worker = repository.get_worker(worker_id)
    if worker is None:
        raise KaamError(404, f"Worker {worker_id} not found")
    today = dt.datetime.now(_IST).date()
    month_start = today.replace(day=1).isoformat()
    coop = tenancy.tenant_id()
    with booking_flow_connection() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS completed_jobs,
                      COALESCE(SUM(amount_paise), 0) AS share_paise,
                      COALESCE(SUM(CASE WHEN DATE(created_at, '+330 minutes') >= ? THEN amount_paise END), 0) AS month_share_paise,
                      COUNT(DISTINCT DATE(created_at, '+330 minutes')) AS engagement_days
               FROM payment_ledger WHERE party = 'worker' AND worker_id = ? AND cooperative_id = ?""",
            (month_start, worker_id, coop),
        ).fetchone()
        billed = conn.execute(
            """SELECT COALESCE(SUM(l.amount_paise), 0) FROM payment_ledger l
               WHERE l.cooperative_id = ? AND l.booking_id IN (SELECT booking_id FROM payment_ledger WHERE party = 'worker' AND worker_id = ? AND cooperative_id = ?
                                      AND DATE(created_at, '+330 minutes') >= ?)""",
            (coop, worker_id, coop, month_start),
        ).fetchone()[0]
        rating_count = conn.execute(
            "SELECT COUNT(*) FROM booking_ratings WHERE worker_id = ? AND cooperative_id = ?", (worker_id, coop)
        ).fetchone()[0]
        awaiting = conn.execute(
            """SELECT COUNT(*) FROM assignments a JOIN bookings b ON b.id = a.booking_id
               WHERE a.cooperative_id = ? AND a.worker_id = ? AND b.status = 'assigned' AND a.accepted_at IS NULL""",
            (coop, worker_id),
        ).fetchone()[0]
    days = row["engagement_days"]
    return WorkerSummary(
        worker_id=worker_id,
        status=worker.status,
        jobs_this_week=worker.jobs_this_week,
        completed_jobs=row["completed_jobs"],
        share_rupees=paise_to_rupees(row["share_paise"]),
        share_this_month_rupees=paise_to_rupees(row["month_share_paise"]),
        billed_this_month_rupees=paise_to_rupees(billed),
        rating=worker.rating,
        rating_count=rating_count,
        engagement_days=days,
        days_to_benefits=max(0, ELIGIBILITY_DAYS - days),
        free_hours_this_week=free_hours(worker.availability, today),
        awaiting_reply=awaiting,
    )


# ── jobs ─────────────────────────────────────────────────────────────────

def jobs(worker_id: int) -> list[WorkerJob]:
    """Newest first: current assignments, completed jobs with money and rating, jobs passed on."""
    out: list[WorkerJob] = []
    coop = tenancy.tenant_id()
    with booking_flow_connection() as conn:
        for r in conn.execute(
            """SELECT b.*, a.created_at AS assigned_at, a.accepted_at, a.start_selfie_url, a.started_at, a.end_photo_url, a.explanation,
                      l.amount_paise AS share_paise, r.rating, r.comment
               FROM assignments a
               JOIN bookings b ON b.id = a.booking_id AND b.cooperative_id = a.cooperative_id
               LEFT JOIN payment_ledger l ON l.booking_id = b.id AND l.cooperative_id = b.cooperative_id AND l.party = 'worker'
               LEFT JOIN booking_ratings r ON r.booking_id = b.id AND r.cooperative_id = b.cooperative_id
               WHERE a.worker_id = ? AND a.cooperative_id = ? ORDER BY a.id DESC""",
            (worker_id, coop),
        ):
            row = dict(r)
            billed = None
            if row["status"] == "completed":
                billed = conn.execute(
                    "SELECT COALESCE(SUM(amount_paise), 0) FROM payment_ledger WHERE booking_id = ?", (row["id"],)
                ).fetchone()[0]
            outcome = "completed" if row["status"] == "completed" else "accepted" if row["accepted_at"] else "assigned"
            settlement = conn.execute(
                "SELECT status, hours_worked, materials_paise, standard_paise, proposed_paise, counter_paise, agreed_paise, customer_note, paid_via, dispute_id "
                "FROM settlements WHERE booking_id = ?", (row["id"],)
            ).fetchone()
            settlement_info = None
            if settlement is not None:
                s = dict(settlement)
                settlement_info = {
                    "status": s["status"], "hours_worked": s["hours_worked"], "customer_note": s["customer_note"], "paid_via": s["paid_via"],
                    "dispute_id": s["dispute_id"],
                    "waiting_on": None if s["status"] == "agreed" else "customer" if s["status"] == "proposed" else "worker" if s["status"] == "countered" else "council",
                    **{k.replace("_paise", "_rupees"): (paise_to_rupees(s[k]) if s[k] is not None else None)
                       for k in ("materials_paise", "standard_paise", "proposed_paise", "counter_paise", "agreed_paise")},
                }
            out.append(WorkerJob(
                booking_id=row["id"], customer_name=row["customer_name"], customer_phone=row.get("customer_phone"),
                trade=row["trade"], address=row.get("address"), latitude=row["latitude"], longitude=row["longitude"],
                scheduled_for=row.get("scheduled_for"), outcome=outcome, assigned_at=row["assigned_at"],
                accepted_at=row["accepted_at"], start_selfie_url=row.get("start_selfie_url"), started_at=row.get("started_at"), end_photo_url=row.get("end_photo_url"), completed_at=row.get("completed_at"), explanation=row.get("explanation"),
                billed_rupees=paise_to_rupees(billed) if billed is not None else None,
                share_rupees=paise_to_rupees(row["share_paise"]) if row["share_paise"] is not None else None,
                rating=row["rating"], rating_comment=row["comment"], settlement=settlement_info,
            ))
        for r in conn.execute(
            """SELECT b.*, d.reason, d.created_at AS declined_at FROM declines d
               JOIN bookings b ON b.id = d.booking_id WHERE d.worker_id = ? ORDER BY d.id DESC""",
            (worker_id,),
        ):
            row = dict(r)
            out.append(WorkerJob(
                booking_id=row["id"], customer_name=row["customer_name"], customer_phone=None, trade=row["trade"],
                address=row.get("address"), latitude=row["latitude"], longitude=row["longitude"],
                scheduled_for=row.get("scheduled_for"), outcome="declined",
                decline_reason=row["reason"], declined_at=row["declined_at"],
            ))
    out.sort(key=lambda j: j.declined_at or j.completed_at or j.assigned_at or "", reverse=True)
    return out


# ── availability edits ───────────────────────────────────────────────────

def replace_availability(worker_id: int, windows: list[AvailabilityWindow]) -> Worker:
    worker = repository.set_worker_availability(worker_id, windows, replace=True)
    if worker is None:
        raise KaamError(404, f"Worker {worker_id} not found")
    return worker


def remove_window(worker_id: int, index: int) -> Worker:
    worker = repository.get_worker(worker_id)
    if worker is None:
        raise KaamError(404, f"Worker {worker_id} not found")
    if not 0 <= index < len(worker.availability):
        raise KaamError(404, f"No availability window #{index}")
    windows = [w for i, w in enumerate(worker.availability) if i != index]
    return repository.set_worker_availability(worker_id, windows, replace=True)  # type: ignore[return-value]


def patch_window(worker_id: int, index: int, patch: WindowPatch) -> Worker:
    worker = repository.get_worker(worker_id)
    if worker is None:
        raise KaamError(404, f"Worker {worker_id} not found")
    if not 0 <= index < len(worker.availability):
        raise KaamError(404, f"No availability window #{index}")
    windows = list(worker.availability)
    current = windows[index]
    updated = current.model_copy(update={k: v for k, v in patch.model_dump().items() if v is not None})
    if updated.end <= updated.start:
        raise KaamError(422, "The end time must be after the start time")
    windows[index] = updated
    return repository.set_worker_availability(worker_id, windows, replace=True)  # type: ignore[return-value]


# ── accept / decline ─────────────────────────────────────────────────────

def _assignment_for(conn: sqlite3.Connection, booking_id: int, worker_id: int) -> dict[str, Any]:
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id = ? AND cooperative_id = ?", (booking_id, tenancy.tenant_id())
    ).fetchone()
    if booking is None:
        raise KaamError(404, f"Booking {booking_id} not found")
    if booking["status"] not in ("assigned", "in_progress"):
        raise KaamError(409, f"Booking {booking_id} is '{booking['status']}'; only an assigned or in-progress job can be acted upon")
    assignment = conn.execute(
        "SELECT * FROM assignments WHERE booking_id = ? AND worker_id = ? AND cooperative_id = ? ORDER BY id DESC LIMIT 1",
        (booking_id, worker_id, tenancy.tenant_id()),
    ).fetchone()
    if assignment is None or assignment["worker_id"] != worker_id:
        raise KaamError(403, "This job is assigned to another worker")
    return dict(assignment)


def accept(booking_id: int, worker_id: int) -> ReplyResult:
    with booking_flow_connection() as conn, immediate_transaction(conn):
        assignment = _assignment_for(conn, booking_id, worker_id)
        if assignment.get("accepted_at") is None:
            conn.execute("UPDATE assignments SET accepted_at = CURRENT_TIMESTAMP WHERE id = ?", (assignment["id"],))
    return ReplyResult(booking_id=booking_id, status="assigned")


def start_work(booking_id: int, worker_id: int, start_selfie_url: str | None = None) -> ReplyResult:
    """Worker arrives on site, uploads verification selfie, and officially begins work."""
    with booking_flow_connection() as conn, immediate_transaction(conn):
        assignment = _assignment_for(conn, booking_id, worker_id)
        conn.execute(
            """UPDATE assignments 
               SET started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                   start_selfie_url = COALESCE(?, start_selfie_url)
               WHERE id = ?""",
            (start_selfie_url, assignment["id"]),
        )
        conn.execute(
            "UPDATE bookings SET status = 'in_progress' WHERE id = ?",
            (booking_id,),
        )
    return ReplyResult(booking_id=booking_id, status="in_progress")


def record_proof_of_work(
    booking_id: int, worker_id: int, start_selfie_url: str | None = None, end_photo_url: str | None = None
) -> dict[str, Any]:
    """Records start selfie or completion proof photo."""
    with booking_flow_connection() as conn, immediate_transaction(conn):
        assignment = _assignment_for(conn, booking_id, worker_id)
        conn.execute(
            """UPDATE assignments 
               SET start_selfie_url = COALESCE(?, start_selfie_url),
                   end_photo_url = COALESCE(?, end_photo_url)
               WHERE id = ?""",
            (start_selfie_url, end_photo_url, assignment["id"]),
        )
    return {
        "booking_id": booking_id,
        "worker_id": worker_id,
        "start_selfie_url": start_selfie_url,
        "end_photo_url": end_photo_url,
        "status": "saved",
    }


def decline(booking_id: int, worker_id: int, body: DeclineRequest) -> ReplyResult:
    """Record the decline, hand the booking back, and offer it to the next-best worker at once."""
    with booking_flow_connection() as conn:
        with immediate_transaction(conn):
            _assignment_for(conn, booking_id, worker_id)
            conn.execute(
                "INSERT INTO declines (booking_id, worker_id, reason, note, cooperative_id) VALUES (?, ?, ?, ?, ?)",
                (booking_id, worker_id, body.reason, (body.note or "").strip() or None, tenancy.tenant_id()),
            )
            conn.execute("DELETE FROM assignments WHERE booking_id = ? AND cooperative_id = ?", (booking_id, tenancy.tenant_id()))
            conn.execute("UPDATE bookings SET status = 'pending' WHERE id = ? AND cooperative_id = ? AND status = 'assigned'", (booking_id, tenancy.tenant_id()))
            conn.execute(
                "UPDATE workers SET jobs_this_week = MAX(0, jobs_this_week - 1) WHERE id = ? AND cooperative_id = ?", (worker_id, tenancy.tenant_id())
            )
            if body.mark_busy_today:
                row = conn.execute("SELECT availability FROM workers WHERE id = ? AND cooperative_id = ?", (worker_id, tenancy.tenant_id())).fetchone()
                windows = json.loads(row["availability"] or "[]")
                now = dt.datetime.now(_IST)
                windows.append(AvailabilityWindow(
                    date=now.date().isoformat(), start=now.strftime("%H:%M"), end="23:59", available=False,
                ).model_dump(mode="json"))
                conn.execute("UPDATE workers SET availability = ? WHERE id = ? AND cooperative_id = ?", (json.dumps(windows), worker_id, tenancy.tenant_id()))
            excluded = tuple(r["worker_id"] for r in conn.execute(
                "SELECT DISTINCT worker_id FROM declines WHERE booking_id = ? AND cooperative_id = ? ORDER BY worker_id",
                (booking_id, tenancy.tenant_id()),
            ))
        try:
            result = booking_flow.assign_booking(conn, booking_id, exclude_worker_ids=excluded)
        except (NoEligibleWorker, InvalidBookingState):
            return ReplyResult(booking_id=booking_id, status="pending")
        except BookingFlowError as exc:
            raise KaamError(exc.status_code, str(exc)) from exc
    worker = result.get("worker") or {}
    return ReplyResult(booking_id=booking_id, status=result["status"], reassigned_to=worker.get("name"))


# ── council approval ─────────────────────────────────────────────────────

def pending_workers() -> list[Worker]:
    return [w for w in repository.list_workers() if w.status == "pending"]


def approve(worker_id: int) -> Worker:
    worker = repository.set_worker_status(worker_id, "active")
    if worker is None:
        raise KaamError(404, f"Worker {worker_id} not found")
    return worker
