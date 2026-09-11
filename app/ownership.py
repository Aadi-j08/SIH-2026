"""
Who may see or act on a booking.

Bookings remember the Ghar account that placed them (bookings.customer_user_id);
assignments name the worker. Council members administer the cooperative and
are never restricted here. Customers see only their own bookings, workers
only the bookings assigned to them. app/repository.py is left as it is; the
one extra write (recording the owner) lives here.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.auth import User
from app.database import connection


def attach_customer(booking_id: int, user: User) -> None:
    """Record which account placed a booking (council bookings are recorded too, for the audit trail)."""
    with connection() as conn:
        conn.execute("UPDATE bookings SET customer_user_id = ? WHERE id = ?", (user.id, booking_id))


def visible_booking_ids(user: User) -> list[int] | None:
    """Booking ids this user may see; None means no restriction (council)."""
    if user.is_council:
        return None
    with connection() as conn:
        if user.access_role == "customer":
            rows = conn.execute("SELECT id FROM bookings WHERE customer_user_id = ?", (user.id,))
        else:  # worker: the bookings assigned to their worker record
            rows = conn.execute("SELECT booking_id AS id FROM assignments WHERE worker_id = ?", (user.worker_id or -1,))
        return [row["id"] for row in rows]


def _owner_id(detail: dict[str, Any]) -> int | None:
    return detail["booking"].get("customer_user_id")


def _assigned_worker_id(detail: dict[str, Any]) -> int | None:
    assignment = detail.get("assignment")
    if not assignment:
        return None
    worker = assignment.get("worker") or {}
    return worker.get("id")


def ensure_can_view(user: User, detail: dict[str, Any]) -> None:
    """Customer: own booking. Worker: booking assigned to them. Council: anything."""
    if user.is_council:
        return
    if user.access_role == "customer" and _owner_id(detail) == user.id:
        return
    if user.access_role == "worker" and user.worker_id is not None and _assigned_worker_id(detail) == user.worker_id:
        return
    raise HTTPException(status_code=403, detail="This booking is not yours to view")


def ensure_customer_owns(user: User, detail: dict[str, Any]) -> None:
    if user.is_council:
        return
    if user.access_role == "customer" and _owner_id(detail) == user.id:
        return
    raise HTTPException(status_code=403, detail="Only the customer who placed this booking can do that")


def ensure_worker_assigned(user: User, detail: dict[str, Any]) -> None:
    if user.is_council:
        return
    if user.access_role == "worker" and user.worker_id is not None and _assigned_worker_id(detail) == user.worker_id:
        return
    raise HTTPException(status_code=403, detail="This job is assigned to another worker")


def ensure_own_worker_record(user: User, worker_id: int) -> None:
    """A worker may only change their own record; council may change anyone's."""
    if user.is_council:
        return
    if user.access_role == "worker" and user.worker_id == worker_id:
        return
    raise HTTPException(status_code=403, detail="You can only update your own availability")
