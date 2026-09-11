"""Booking flow endpoints. Include in app/main.py with app.include_router(router)."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException

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
        raise HTTPException(status_code=500, detail=f"Allocation bridge error: {exc}") from exc


@router.post("/bookings/{booking_id}/assign", response_model=AssignmentResult)
def assign_booking(booking_id: int):
    """Pick the top worker with the fair allocation engine and assign atomically."""
    return _run(booking_flow.assign_booking, booking_id)


@router.get("/bookings/{booking_id}", response_model=BookingDetail)
def get_booking(booking_id: int):
    """Booking with its assignment, payment ledger and rating."""
    return _run(booking_flow.get_booking_detail, booking_id)


@router.post("/bookings/{booking_id}/complete", response_model=CompletionResult)
def complete_booking(booking_id: int, body: CompleteBookingRequest):
    """Mark an assigned booking completed and write the mock 85/10/5 ledger."""
    return _run(booking_flow.complete_booking, booking_id, body.amount)


@router.post("/bookings/{booking_id}/rating", response_model=RatingResult)
def rate_booking(booking_id: int, body: RatingRequest):
    """Rate a completed booking once; updates the worker's average rating."""
    return _run(booking_flow.rate_booking, booking_id, body.rating, body.comment)


@router.get("/admin/dashboard", response_model=AdminDashboard)
def admin_dashboard():
    """Booking counts, money split, ratings, fairness and per-worker engagement days."""
    return _run(booking_flow.admin_dashboard)
