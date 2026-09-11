"""Request and response models for the booking flow endpoints.

Kept separate so app/schemas.py stays untouched; move them there if you prefer.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AssignmentResult(BaseModel):
    booking_id: int
    status: str
    assignment_id: int
    worker: dict[str, Any]
    score: float
    score_breakdown: Any
    explanation: str


class CompleteBookingRequest(BaseModel):
    amount: Decimal = Field(
        gt=0, max_digits=9, decimal_places=2,
        description="Final bill in rupees, e.g. 500 or 349.50",
    )


class LedgerEntry(BaseModel):
    party: str
    share_percent: int
    amount_paise: int
    amount_rupees: float
    worker_id: int | None = None


class CompletionResult(BaseModel):
    booking_id: int
    status: str
    worker_id: int
    amount_rupees: float
    ledger: list[LedgerEntry]


class RatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class RatingResult(BaseModel):
    booking_id: int
    worker_id: int
    rating: int
    worker_average_rating: float | None
    worker_rating_count: int


class BookingDetail(BaseModel):
    booking: dict[str, Any]
    assignment: dict[str, Any] | None
    payment_ledger: list[LedgerEntry]
    rating: dict[str, Any] | None


class AdminDashboard(BaseModel):
    bookings: dict[str, int]
    money: dict[str, float]
    ratings: dict[str, Any]
    fairness: dict[str, Any]
    workers: list[dict[str, Any]]
    recent_assignments: list[dict[str, Any]]
