"""
Data contracts shared by the API, the repository and the AI services.

Pydantic v2 models. The allocation engine works on ServiceRequest and
WorkerProfile; the booking flow's bridge builds those from raw SQLite rows,
so their field names match the column names in app/database.py.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.trades import canonical_trade

Weekday = Literal[0, 1, 2, 3, 4, 5, 6]  # 0 = Monday


# ── availability (produced by the voice parser, consumed by allocation) ──

class AvailabilityWindow(BaseModel):
    """A block of time a worker has declared free (or busy, when available=False).

    date takes precedence over weekday; if both are None the window recurs
    every day.
    """
    date: dt.date | None = None
    weekday: Weekday | None = None
    start: str = Field(default="00:00", pattern=r"^\d{2}:\d{2}$")
    end: str = Field(default="23:59", pattern=r"^\d{2}:\d{2}$")
    available: bool = True


# ── workers ──────────────────────────────────────────────────────────────

class WorkerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    trade: str = Field(min_length=1, max_length=50, description="e.g. plumbing, electrical, carpentry")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    phone: str | None = Field(default=None, max_length=20)
    rating: float | None = Field(default=None, ge=1, le=5)
    availability: list[AvailabilityWindow] = Field(default_factory=list)

    @field_validator("trade")
    @classmethod
    def _canonical_trade(cls, value: str) -> str:
        return canonical_trade(value)


class Worker(WorkerCreate):
    id: int
    jobs_this_week: int = 0
    created_at: str | None = None


class WorkerProfile(BaseModel):
    """What the allocation engine needs to know about a worker."""
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str = ""
    trade: str
    latitude: float
    longitude: float
    jobs_this_week: int = 0
    rating: float | None = None
    availability: list[AvailabilityWindow] = Field(default_factory=list)


# ── bookings ─────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    trade: str = Field(min_length=1, max_length=50)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    scheduled_for: dt.datetime | None = Field(default=None, description="Requested slot; None = as soon as possible")
    customer_phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=300)

    @field_validator("trade")
    @classmethod
    def _canonical_trade(cls, value: str) -> str:
        return canonical_trade(value)


class Booking(BookingCreate):
    id: int
    status: str = "pending"
    customer_user_id: int | None = None
    created_at: str | None = None


# ── allocation engine ────────────────────────────────────────────────────

class ServiceRequest(BaseModel):
    """A job to be allocated. Built from a bookings row or sent directly by a client."""
    model_config = ConfigDict(extra="ignore")

    booking_id: int | None = None
    trade: str
    latitude: float
    longitude: float
    scheduled_for: dt.datetime | None = None
    max_distance_km: float = Field(default=15.0, gt=0)

    @field_validator("trade")
    @classmethod
    def _canonical_trade(cls, value: str) -> str:
        return canonical_trade(value)


class Recommendation(BaseModel):
    rank: int
    worker_id: int
    worker_name: str
    distance_km: float
    score: float
    score_breakdown: dict[str, float]
    explanation: str
    why_selected: list[str] = Field(default_factory=list)


# ── voice availability ───────────────────────────────────────────────────

class VoiceAvailabilityRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=500, description="Speech-to-text output, Hindi/English/Hinglish")
    reference_date: dt.date | None = Field(default=None, description="Day 'aaj'/'kal' are relative to; default today")
    replace: bool = Field(default=True, description="Replace the worker's existing windows (False = append)")
    confirmed: bool = Field(default=False, description="Worker confirmed a low-confidence interpretation")


class VoiceAvailabilityResult(BaseModel):
    transcript: str
    language: Literal["hi", "en", "mixed", "unknown"]
    windows: list[AvailabilityWindow]
    confidence: float = Field(ge=0, le=1)
    summary: str
    unrecognised: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    can_save: bool = False
    confirmation_message: str | None = None


class VoiceAvailabilityResponse(BaseModel):
    parsed: VoiceAvailabilityResult
    worker: Worker


# ── demand forecast ──────────────────────────────────────────────────────

class ForecastPoint(BaseModel):
    date: dt.date
    weekday: str
    already_booked: int = 0
    expected_bookings: float
    lower: float
    upper: float
    workers_needed: int


class DemandForecast(BaseModel):
    trade: str | None
    horizon_days: int
    history_days: int
    history_bookings: int
    method: str
    total_expected: float
    points: list[ForecastPoint]


# ── staffing (forecast vs. available workers) ────────────────────────────

class StaffingDay(BaseModel):
    date: dt.date
    weekday: str
    expected_bookings: float
    workers_needed: int
    available_workers: int
    shortage: int


class StaffingForecast(BaseModel):
    """Does the cooperative have enough workers of one trade for the coming days?"""
    trade: str
    area: str | None
    horizon_days: int
    peak_day: dt.date | None
    expected_bookings: float = Field(description="Expected bookings on the peak day")
    workers_needed: int = Field(description="Workers to keep on call on the peak day")
    available_workers: int = Field(description="Eligible workers not declared busy on the peak day")
    shortage: int
    recommendation: str
    days: list[StaffingDay]
