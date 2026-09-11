"""Booking flow endpoints. Include in app/main.py with app.include_router(router).

Who may call what:
  POST /bookings/{id}/assign      council
  GET  /bookings/{id}             the customer who placed it, the worker assigned to it, council
  POST /bookings/{id}/complete    the worker assigned to it, council
  POST /bookings/{id}/rating      the customer who placed it, council
  GET  /admin/dashboard           council
"""
from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app import ownership
from app.auth import User, require_council, require_customer, require_user, require_worker
from app.booking_flow_db import booking_flow_connection
from app.booking_flow_schemas import (
    AdminDashboard,
    AssignmentResult,
    BookingDetail,
    CompleteBookingRequest,
    CompletionResult,
    RatingRequest,
    RatingResult,
)
from app.services import booking_flow
from app.services.allocation_bridge import AllocationBridgeError

log = logging.getLogger("sahakarsetu.booking_flow")
router = APIRouter(tags=["booking flow"])


def _run(operation: Callable[..., Any], *args: Any) -> Any:
    # The connection is opened inside the endpoint's own thread; sqlite3
    # connections must not be shared across FastAPI's threadpool workers.
    try:
        with booking_flow_connection() as conn:
            return operation(conn, *args)
    except booking_flow.BookingFlowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except AllocationBridgeError as exc:
        log.error("allocation bridge could not process the request: %s", exc)
        raise HTTPException(status_code=500, detail="The allocation engine could not process this booking.") from exc
    except sqlite3.IntegrityError as exc:
        # A database rule said no (e.g. a second assignment for the same booking).
        # The trigger messages are ours and safe to show; anything else stays generic.
        message = str(exc)
        detail = message if message and "constraint" not in message.lower() else "That change conflicts with an existing record."
        log.info("integrity rule rejected a write: %s", message)
        raise HTTPException(status_code=409, detail=detail) from exc
    except sqlite3.OperationalError as exc:
        # Surface transient lock/schema failures as retryable responses rather
        # than allowing an opaque 500 during concurrent dashboard polling.
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise HTTPException(status_code=503, detail="The database is busy; please retry.") from exc
        raise


def _detail_for(user: User, booking_id: int, check: Callable[[User, dict[str, Any]], None]) -> dict[str, Any]:
    """Load a booking and apply an ownership rule before anything is written."""
    detail = _run(booking_flow.get_booking_detail, booking_id)
    check(user, detail)
    return detail


@router.post("/bookings/{booking_id}/assign", response_model=AssignmentResult)
def assign_booking(booking_id: int, user: User = Depends(require_council)):
    """Pick the top worker with the fair allocation engine and assign atomically. Council only."""
    result = _run(booking_flow.assign_booking, booking_id)
    log.info("booking %s assigned to worker %s by %s #%s", booking_id, result["worker"]["id"], user.access_role, user.id)
    return result


@router.get("/bookings/{booking_id}", response_model=BookingDetail)
def get_booking(booking_id: int, user: User = Depends(require_user)):
    """Booking with its assignment, payment ledger and rating — for its customer, its worker, or the council."""
    return _detail_for(user, booking_id, ownership.ensure_can_view)


@router.post("/bookings/{booking_id}/complete", response_model=CompletionResult)
def complete_booking(booking_id: int, body: CompleteBookingRequest, user: User = Depends(require_worker)):
    """Mark an assigned booking completed and write the mock 85/10/5 ledger. The assigned worker, or council."""
    _detail_for(user, booking_id, ownership.ensure_worker_assigned)
    result = _run(booking_flow.complete_booking, booking_id, body.amount)
    log.info("booking %s completed for %s rupees by %s #%s", booking_id, body.amount, user.access_role, user.id)
    return result


@router.post("/bookings/{booking_id}/rating", response_model=RatingResult)
def rate_booking(booking_id: int, body: RatingRequest, user: User = Depends(require_customer)):
    """Rate a completed booking once; updates the worker's average rating. The booking's customer, or council."""
    _detail_for(user, booking_id, ownership.ensure_customer_owns)
    return _run(booking_flow.rate_booking, booking_id, body.rating, body.comment)


@router.get("/admin/dashboard", response_model=AdminDashboard)
def admin_dashboard(_: User = Depends(require_council)):
    """Booking counts, money split, ratings, fairness and per-worker engagement days. Council only."""
    return _run(booking_flow.admin_dashboard)
