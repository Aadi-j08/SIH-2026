"""
Booking lifecycle on top of the existing SQLite tables:

    pending --assign--> assigned --complete--> completed --rating--> (rated)

Every state change runs inside one immediate transaction, so its writes
either all happen or none do.
"""
from __future__ import annotations

import json
import sqlite3
from decimal import Decimal
from typing import Any

from app.booking_flow_db import (
    ASSIGNMENT_SCORE_COLUMNS,
    WORKER_NAME_COLUMNS,
    WORKER_RATING_COLUMNS,
    immediate_transaction,
    pick_column,
    table_columns,
)
from app.services.allocation_bridge import AllocationBridgeError, top_recommendation
from app.services.ledger import SPLIT_PERCENT, paise_to_rupees, rupees_to_paise, split_payment

PENDING, ASSIGNED, COMPLETED = "pending", "assigned", "completed"

# Prototype cooperative eligibility threshold: 90 engagement days.
# This is configurable and is not a legal claim.
ELIGIBILITY_DAYS = 90
# Ledger timestamps are UTC (CURRENT_TIMESTAMP); engagement days are counted in IST.
_IST = "'+330 minutes'"


class BookingFlowError(Exception):
    status_code = 400


class BookingNotFound(BookingFlowError):
    status_code = 404


class InvalidBookingState(BookingFlowError):
    status_code = 409


class NoEligibleWorker(BookingFlowError):
    status_code = 409


class AlreadyRated(BookingFlowError):
    status_code = 409


# ── helpers ──────────────────────────────────────────────────────────────

def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _get_booking(conn: sqlite3.Connection, booking_id: int) -> dict[str, Any]:
    booking = _row(conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone())
    if booking is None:
        raise BookingNotFound(f"Booking {booking_id} not found")
    return booking


def _get_worker(conn: sqlite3.Connection, worker_id: int) -> dict[str, Any] | None:
    return _row(conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone())


def _latest_assignment(conn: sqlite3.Connection, booking_id: int) -> dict[str, Any] | None:
    return _row(conn.execute(
        "SELECT * FROM assignments WHERE booking_id = ? ORDER BY id DESC LIMIT 1", (booking_id,)
    ).fetchone())


def _decode_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _ledger_entries(conn: sqlite3.Connection, booking_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT party, share_percent, amount_paise, worker_id FROM payment_ledger "
        "WHERE booking_id = ? ORDER BY share_percent DESC", (booking_id,)
    ).fetchall()
    return [
        {**dict(r), "amount_rupees": paise_to_rupees(r["amount_paise"])}
        for r in rows
    ]


def _increment_worker_jobs(conn: sqlite3.Connection, worker_id: int) -> None:
    cursor = conn.execute(
        "UPDATE workers SET jobs_this_week = COALESCE(jobs_this_week, 0) + 1 WHERE id = ?",
        (worker_id,),
    )
    if cursor.rowcount != 1:
        raise AllocationBridgeError(f"Selected worker {worker_id} does not exist")


# ── POST /bookings/{id}/assign ───────────────────────────────────────────

def assign_booking(
    conn: sqlite3.Connection, booking_id: int, exclude_worker_ids: tuple[int, ...] = ()
) -> dict[str, Any]:
    """exclude_worker_ids: workers who already passed on this booking (see app/kaam.py). Workers still
    awaiting council approval (workers.status = 'pending') are never offered work."""
    with immediate_transaction(conn):
        booking = _get_booking(conn, booking_id)                       # 1. load booking
        if booking["status"] != PENDING:
            raise InvalidBookingState(
                f"Booking {booking_id} is '{booking['status']}'; only pending bookings can be assigned"
            )
        # Always exclude workers who already declined this specific booking,
        # even when called without explicit exclude_worker_ids (e.g. council assign).
        declined = {r["worker_id"] for r in conn.execute(
            "SELECT worker_id FROM declines WHERE booking_id = ?", (booking_id,)
        )} if "declines" in {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} else set()
        all_excluded = set(exclude_worker_ids) | declined

        status_filter = "WHERE COALESCE(status, 'active') = 'active'" if "status" in table_columns(conn, "workers") else ""
        workers = [                                                     # 2. load workers
            dict(r) for r in conn.execute(f"SELECT * FROM workers {status_filter}")
            if r["id"] not in all_excluded
        ]
        best = top_recommendation(booking, workers)                    # 3–5. schema, engine, top pick
        if best is None:
            raise NoEligibleWorker(f"No eligible worker found for booking {booking_id}")
        if not any(w["id"] == best.worker_id for w in workers):
            raise AllocationBridgeError(f"Engine returned unknown worker {best.worker_id}")

        columns = table_columns(conn, "assignments")                   # 6. assignment record
        score_column = pick_column(conn, "assignments", ASSIGNMENT_SCORE_COLUMNS) or "allocation_score"
        record = {"booking_id": booking_id, "worker_id": best.worker_id, score_column: best.score}
        if "score_breakdown" in columns:
            record["score_breakdown"] = json.dumps(best.score_breakdown, default=str)
        if "explanation" in columns:
            record["explanation"] = best.explanation
        placeholders = ", ".join("?" for _ in record)
        cursor = conn.execute(
            f"INSERT INTO assignments ({', '.join(record)}) VALUES ({placeholders})",
            tuple(record.values()),
        )
        assignment_id = cursor.lastrowid

        updated = conn.execute(                                         # 7. pending -> assigned
            "UPDATE bookings SET status = ? WHERE id = ? AND status = ?",
            (ASSIGNED, booking_id, PENDING),
        )
        if updated.rowcount != 1:
            raise InvalidBookingState(f"Booking {booking_id} changed state during assignment")

        _increment_worker_jobs(conn, best.worker_id)                   # 8. jobs_this_week + 1
        worker = _get_worker(conn, best.worker_id)

    return {                                                            # 9. response
        "booking_id": booking_id,
        "status": ASSIGNED,
        "assignment_id": assignment_id,
        "worker": worker,
        "score": best.score,
        "score_breakdown": best.score_breakdown,
        "explanation": best.explanation,
    }


# ── GET /bookings/{id} ───────────────────────────────────────────────────

def verify_arrival(conn: sqlite3.Connection, booking_id: int, worker_id: int, photo_uri: str) -> None:
    with immediate_transaction(conn):
        assignment = _latest_assignment(conn, booking_id)
        if not assignment or assignment["worker_id"] != worker_id:
            raise BookingFlowError(403, "You are not assigned to this booking.")
        conn.execute(
            "UPDATE assignments SET start_selfie_url = ? WHERE booking_id = ?",
            (photo_uri, booking_id)
        )

def start_work(conn: sqlite3.Connection, booking_id: int, worker_id: int, timestamp: str) -> None:
    with immediate_transaction(conn):
        assignment = _latest_assignment(conn, booking_id)
        if not assignment or assignment["worker_id"] != worker_id:
            raise BookingFlowError(403, "You are not assigned to this booking.")
        if "start_selfie_url" in assignment and not assignment["start_selfie_url"]:
            raise BookingFlowError(400, "You must verify arrival before starting work.")
        conn.execute(
            "UPDATE assignments SET started_at = ? WHERE booking_id = ?",
            (timestamp, booking_id)
        )

def verify_completion(conn: sqlite3.Connection, booking_id: int, worker_id: int, photo_uri: str) -> None:
    with immediate_transaction(conn):
        assignment = _latest_assignment(conn, booking_id)
        if not assignment or assignment["worker_id"] != worker_id:
            raise BookingFlowError(403, "You are not assigned to this booking.")
        if "started_at" in assignment and not assignment["started_at"]:
            raise BookingFlowError(400, "You must start the job before submitting completion proof.")
        conn.execute(
            "UPDATE assignments SET end_photo_url = ? WHERE booking_id = ?",
            (photo_uri, booking_id)
        )


def get_booking_detail(conn: sqlite3.Connection, booking_id: int) -> dict[str, Any]:
    booking = _get_booking(conn, booking_id)
    assignment = _latest_assignment(conn, booking_id)
    if assignment is not None:
        score_column = pick_column(conn, "assignments", ASSIGNMENT_SCORE_COLUMNS) or "allocation_score"
        worker = _get_worker(conn, assignment["worker_id"])
        assignment = {
            "assignment_id": assignment["id"],
            "worker": worker,
            "score": assignment.get(score_column),
            "score_breakdown": _decode_json(assignment.get("score_breakdown")),
            "explanation": assignment.get("explanation"),
            "assigned_at": assignment.get("created_at"),
            "accepted_at": assignment.get("accepted_at"),
            "start_selfie_url": assignment.get("start_selfie_url"),
            "started_at": assignment.get("started_at"),
            "end_photo_url": assignment.get("end_photo_url"),
        }
    rating = _row(conn.execute(
        "SELECT rating, comment, created_at FROM booking_ratings WHERE booking_id = ?", (booking_id,)
    ).fetchone())
    return {
        "booking": booking,
        "assignment": assignment,
        "payment_ledger": _ledger_entries(conn, booking_id),
        "rating": rating,
    }


def cancel_booking(conn: sqlite3.Connection, booking_id: int) -> dict[str, Any]:
    with immediate_transaction(conn):
        booking = _get_booking(conn, booking_id)
        if booking["status"] == COMPLETED:
            raise InvalidBookingState(f"Booking {booking_id} is already completed and cannot be cancelled")
        if booking["status"] == "cancelled":
            return {"booking_id": booking_id, "status": "cancelled"}
        conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
        return {"booking_id": booking_id, "status": "cancelled"}


# ── POST /bookings/{id}/complete ─────────────────────────────────────────

def complete_booking(conn: sqlite3.Connection, booking_id: int, amount: Decimal) -> dict[str, Any]:
    amount_paise = rupees_to_paise(amount)
    shares = split_payment(amount_paise)
    with immediate_transaction(conn):
        booking = _get_booking(conn, booking_id)
        if booking["status"] != ASSIGNED:
            raise InvalidBookingState(
                f"Booking {booking_id} is '{booking['status']}'; only assigned bookings can be completed"
            )
        assignment = _latest_assignment(conn, booking_id)
        if assignment is None:
            raise InvalidBookingState(f"Booking {booking_id} has no assignment record")
        worker_id = assignment["worker_id"]

        for party, paise in shares.items():
            conn.execute(
                "INSERT INTO payment_ledger (booking_id, worker_id, party, share_percent, amount_paise) "
                "VALUES (?, ?, ?, ?, ?)",
                (booking_id, worker_id if party == "worker" else None, party, SPLIT_PERCENT[party], paise),
            )
        updated = conn.execute(
            "UPDATE bookings SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
            (COMPLETED, booking_id, ASSIGNED),
        )
        if updated.rowcount != 1:
            raise InvalidBookingState(f"Booking {booking_id} changed state during completion")
        ledger = _ledger_entries(conn, booking_id)

    return {
        "booking_id": booking_id,
        "status": COMPLETED,
        "worker_id": worker_id,
        "amount_rupees": paise_to_rupees(amount_paise),
        "ledger": ledger,
    }


# ── POST /bookings/{id}/rating ───────────────────────────────────────────

def rate_booking(conn: sqlite3.Connection, booking_id: int, rating: int, comment: str | None) -> dict[str, Any]:
    with immediate_transaction(conn):
        booking = _get_booking(conn, booking_id)
        if booking["status"] != COMPLETED:
            raise InvalidBookingState(
                f"Booking {booking_id} is '{booking['status']}'; only completed bookings can be rated"
            )
        if conn.execute("SELECT 1 FROM booking_ratings WHERE booking_id = ?", (booking_id,)).fetchone():
            raise AlreadyRated(f"Booking {booking_id} has already been rated")
        assignment = _latest_assignment(conn, booking_id)
        if assignment is None:
            raise InvalidBookingState(f"Booking {booking_id} has no assignment record")
        worker_id = assignment["worker_id"]

        conn.execute(
            "INSERT INTO booking_ratings (booking_id, worker_id, rating, comment) VALUES (?, ?, ?, ?)",
            (booking_id, worker_id, rating, comment),
        )
        count, total = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(rating), 0) FROM booking_ratings WHERE worker_id = ?",
            (worker_id,),
        ).fetchone()

        average = None
        rating_column = pick_column(conn, "workers", WORKER_RATING_COLUMNS)
        if rating_column:
            worker = _get_worker(conn, worker_id)
            # The worker's starting rating counts as one vote, so one bad review
            # doesn't erase their history.
            base = worker.get("base_rating")
            if base is None:
                base = worker.get(rating_column)
            votes, points = (count + 1, total + base) if base is not None else (count, total)
            average = round(points / votes, 2)
            conn.execute(
                f"UPDATE workers SET {rating_column} = ?, base_rating = ?, rating_count = ? WHERE id = ?",
                (average, base, count, worker_id),
            )

    return {
        "booking_id": booking_id,
        "worker_id": worker_id,
        "rating": rating,
        "worker_average_rating": average,
        "worker_rating_count": count,
    }


# ── GET /admin/dashboard ─────────────────────────────────────────────────

def gini(values: list[float]) -> float:
    """0 = work shared perfectly evenly, 1 = one worker gets everything."""
    data = sorted(v for v in values if v is not None)
    n, total = len(data), sum(data)
    if n == 0 or total == 0:
        return 0.0
    weighted = sum((i + 1) * v for i, v in enumerate(data))
    return round((2 * weighted) / (n * total) - (n + 1) / n, 3)


def admin_dashboard(conn: sqlite3.Connection) -> dict[str, Any]:
    status_counts = {r[0]: r[1] for r in conn.execute("SELECT status, COUNT(*) FROM bookings GROUP BY status")}
    bookings = {"total": sum(status_counts.values())}
    for status in (PENDING, ASSIGNED, COMPLETED):
        bookings[status] = status_counts.get(status, 0)

    party_totals = {r[0]: r[1] for r in conn.execute(
        "SELECT party, SUM(amount_paise) FROM payment_ledger GROUP BY party"
    )}
    money = {
        "gross_rupees": paise_to_rupees(sum(party_totals.values())),
        "worker_payouts_rupees": paise_to_rupees(party_totals.get("worker", 0)),
        "welfare_fund_rupees": paise_to_rupees(party_totals.get("welfare_fund", 0)),
        "platform_operations_rupees": paise_to_rupees(party_totals.get("platform_operations", 0)),
    }

    rating_count, rating_avg = conn.execute("SELECT COUNT(*), AVG(rating) FROM booking_ratings").fetchone()
    ratings = {"count": rating_count, "average": round(rating_avg, 2) if rating_avg is not None else None}

    earnings = {r["worker_id"]: dict(r) for r in conn.execute(
        f"""SELECT worker_id,
                   COUNT(*) AS completed_jobs,
                   SUM(amount_paise) AS earnings_paise,
                   COUNT(DISTINCT DATE(created_at, {_IST})) AS engagement_days
            FROM payment_ledger WHERE party = 'worker' GROUP BY worker_id"""
    )}
    name_column = pick_column(conn, "workers", WORKER_NAME_COLUMNS)
    rating_column = pick_column(conn, "workers", WORKER_RATING_COLUMNS)
    workers = []
    for row in conn.execute("SELECT * FROM workers ORDER BY id"):
        w = dict(row)
        stats = earnings.get(w["id"], {})
        days = stats.get("engagement_days", 0)
        workers.append({
            "id": w["id"],
            "name": w.get(name_column) if name_column else None,
            "jobs_this_week": w.get("jobs_this_week") or 0,
            "rating": w.get(rating_column) if rating_column else None,
            "completed_jobs": stats.get("completed_jobs", 0),
            "earnings_rupees": paise_to_rupees(stats.get("earnings_paise") or 0),
            "engagement_days": days,
            "days_to_social_security_eligibility": max(0, ELIGIBILITY_DAYS - days),
        })

    jobs = [w["jobs_this_week"] for w in workers]
    fairness = {
        "jobs_this_week_min": min(jobs, default=0),
        "jobs_this_week_max": max(jobs, default=0),
        "jobs_this_week_mean": round(sum(jobs) / len(jobs), 2) if jobs else 0.0,
        "jobs_gini": gini(jobs),
        "workers_with_no_jobs_this_week": sum(1 for j in jobs if j == 0),
    }

    score_column = pick_column(conn, "assignments", ASSIGNMENT_SCORE_COLUMNS) or "allocation_score"
    recent = [dict(r) for r in conn.execute(
        f"""SELECT a.id AS assignment_id, a.booking_id, a.worker_id,
                   a.{score_column} AS score, b.status AS booking_status
            FROM assignments a JOIN bookings b ON b.id = a.booking_id
            ORDER BY a.id DESC LIMIT 5"""
    )]
    names = {w["id"]: w["name"] for w in workers}
    for item in recent:
        item["worker_name"] = names.get(item["worker_id"])

    return {
        "bookings": bookings,
        "money": money,
        "ratings": ratings,
        "fairness": fairness,
        "workers": workers,
        "recent_assignments": recent,
    }
