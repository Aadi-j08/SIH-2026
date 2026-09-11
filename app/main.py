"""
SahakarSetu API.

A cooperative-run platform that matches household service requests with
local skilled workers fairly, lets workers declare availability by voice,
and forecasts demand so the cooperative can plan.

Run locally:   .venv/Scripts/uvicorn app.main:app --reload   (docs at /docs)
Web app:       built from frontend/ (npm run build) and served at /app
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app import database, ownership, repository
from app.auth import User, require_council, require_customer, require_user, require_worker
from app.routers.auth import router as auth_router
from app.routers.booking_flow import router as booking_flow_router
from app.schemas import (
    Booking,
    BookingCreate,
    DemandForecast,
    Recommendation,
    ServiceRequest,
    StaffingForecast,
    VoiceAvailabilityRequest,
    VoiceAvailabilityResponse,
    VoiceAvailabilityResult,
    Worker,
    WorkerCreate,
)
from app.services import allocation, forecast, staffing, voice
from app.trades import canonical_trade

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sahakarsetu")


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="SahakarSetu",
    version="0.1.0",
    description="Fair work allocation, voice availability and demand forecasting for a workers' cooperative.",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(booking_flow_router)


# ── errors: clean messages out, details in the log ───────────────────────

@app.exception_handler(sqlite3.IntegrityError)
async def integrity_error(_: Request, exc: sqlite3.IntegrityError) -> JSONResponse:
    message = str(exc)
    log.info("integrity rule rejected a write: %s", message)
    # Trigger messages are written by us and safe to show; raw constraint text is not.
    detail = message if message and "constraint" not in message.lower() else "That change conflicts with an existing record."
    return JSONResponse(status_code=409, content={"detail": detail})


@app.exception_handler(sqlite3.OperationalError)
async def operational_error(_: Request, exc: sqlite3.OperationalError) -> JSONResponse:
    if "locked" in str(exc).lower() or "busy" in str(exc).lower():
        return JSONResponse(status_code=503, content={"detail": "The database is busy; please retry."})
    log.exception("database error")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
FRONTEND_PUBLIC = FRONTEND_DIR / "public"   # static files (photos) picked up without a rebuild


@app.get("/", tags=["health"])
def root() -> dict:
    return {"name": "SahakarSetu", "status": "ok", "docs": "/docs", "app": "/app/"}


# ── web app (React PWA built into frontend/dist) ─────────────────────────

@app.get("/app", include_in_schema=False)
@app.get("/app/{path:path}", include_in_schema=False)
def web_app(path: str = "") -> FileResponse:
    """Serve the built frontend; unknown paths fall back to index.html so the SPA router can handle them."""
    if not FRONTEND_DIST.is_dir():
        raise HTTPException(status_code=404, detail="Frontend not built. Run `npm install && npm run build` in frontend/.")
    for base in (FRONTEND_DIST, FRONTEND_PUBLIC):
        target = (base / path).resolve() if path else base / "index.html"
        if path and target.is_file() and base in target.parents:
            return FileResponse(target)
    if "." in path.rsplit("/", 1)[-1]:      # looks like a file (image, script): a real 404, not the SPA shell
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(FRONTEND_DIST / "index.html")


# ── workers ──────────────────────────────────────────────────────────────

@app.post("/workers", response_model=Worker, status_code=201, tags=["workers"])
def create_worker(body: WorkerCreate, user: User = Depends(require_council)) -> Worker:
    """Register a worker on the cooperative's behalf. Council only (workers self-register via /auth/signup)."""
    worker = repository.create_worker(body)
    log.info("worker %s (%s) registered by council #%s", worker.id, worker.trade, user.id)
    return worker


@app.get("/workers", response_model=list[Worker], tags=["workers"])
def list_workers(trade: str | None = None, _: User = Depends(require_council)) -> list[Worker]:
    """The worker directory (phone numbers included), so council only."""
    return repository.list_workers(canonical_trade(trade) if trade else None)


@app.get("/workers/{worker_id}", response_model=Worker, tags=["workers"])
def get_worker(worker_id: int, user: User = Depends(require_worker)) -> Worker:
    """A worker's own record, or any record for the council."""
    ownership.ensure_own_worker_record(user, worker_id)
    worker = repository.get_worker(worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
    return worker


@app.post("/workers/{worker_id}/availability/voice", response_model=VoiceAvailabilityResponse, tags=["workers", "voice"])
def set_availability_by_voice(
    worker_id: int, body: VoiceAvailabilityRequest, user: User = Depends(require_worker)
) -> VoiceAvailabilityResponse:
    """Parse a spoken availability sentence (Hindi/English/Hinglish) and store it on the worker's own record."""
    ownership.ensure_own_worker_record(user, worker_id)
    if repository.get_worker(worker_id) is None:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
    parsed = voice.parse_availability(body.transcript, body.reference_date)
    if not parsed.windows:
        raise HTTPException(
            status_code=422,
            detail={"message": "Could not understand any availability in the transcript",
                    "parsed": parsed.model_dump(mode="json")},
        )
    worker = repository.set_worker_availability(worker_id, parsed.windows, replace=body.replace)
    return VoiceAvailabilityResponse(parsed=parsed, worker=worker)


@app.post("/voice/parse", response_model=VoiceAvailabilityResult, tags=["voice"])
def parse_voice(body: VoiceAvailabilityRequest) -> VoiceAvailabilityResult:
    """Dry run of the voice parser: see what a transcript would be understood as, without saving."""
    return voice.parse_availability(body.transcript, body.reference_date)


# ── bookings ─────────────────────────────────────────────────────────────

@app.post("/bookings", response_model=Booking, status_code=201, tags=["bookings"])
def create_booking(body: BookingCreate, user: User = Depends(require_customer)) -> Booking:
    """Place a booking. It belongs to the signed-in customer (or to the council member placing it on a household's behalf)."""
    booking = repository.create_booking(body)
    ownership.attach_customer(booking.id, user)
    log.info("booking %s (%s) placed by %s #%s", booking.id, booking.trade, user.access_role, user.id)
    return repository.get_booking(booking.id) or booking


@app.get("/bookings", response_model=list[Booking], tags=["bookings"])
def list_bookings(status: str | None = None, trade: str | None = None, user: User = Depends(require_user)) -> list[Booking]:
    """Bookings the caller may see: their own (customer), those assigned to them (worker), all of them (council)."""
    if status is not None and status not in database.BOOKING_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(database.BOOKING_STATUSES)}")
    bookings = repository.list_bookings(status=status, trade=canonical_trade(trade) if trade else None)
    visible = ownership.visible_booking_ids(user)
    if visible is None:
        return bookings
    allowed = set(visible)
    return [b for b in bookings if b.id in allowed]


class PublicStats(BaseModel):
    """Headline numbers anyone may see (the landing page shows them)."""
    workers: int
    bookings_completed: int
    welfare_fund_rupees: float
    average_rating: float | None


@app.get("/stats", response_model=PublicStats, tags=["health"])
def public_stats() -> PublicStats:
    from app.booking_flow_db import booking_flow_connection
    from app.services.booking_flow import admin_dashboard

    with booking_flow_connection() as conn:
        dashboard = admin_dashboard(conn)
    return PublicStats(
        workers=len(dashboard["workers"]),
        bookings_completed=dashboard["bookings"]["completed"],
        welfare_fund_rupees=dashboard["money"]["welfare_fund_rupees"],
        average_rating=dashboard["ratings"]["average"],
    )


# ── allocation ───────────────────────────────────────────────────────────

@app.get("/bookings/{booking_id}/recommendations", response_model=list[Recommendation], tags=["allocation"])
def booking_recommendations(
    booking_id: int, top_k: int = Query(default=3, ge=1, le=20), _: User = Depends(require_council)
) -> list[Recommendation]:
    """Preview the fair allocation ranking for a booking without assigning anyone. Council only."""
    booking = repository.get_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    request = ServiceRequest(
        booking_id=booking.id, trade=booking.trade, latitude=booking.latitude,
        longitude=booking.longitude, scheduled_for=booking.scheduled_for,
    )
    return allocation.recommend_workers(request, repository.worker_profiles(), top_k=top_k)


@app.post("/allocation/recommend", response_model=list[Recommendation], tags=["allocation"])
def recommend(
    request: ServiceRequest, top_k: int = Query(default=3, ge=1, le=20), _: User = Depends(require_council)
) -> list[Recommendation]:
    """Rank workers for an ad-hoc service request (no booking record needed). Council only."""
    return allocation.recommend_workers(request, repository.worker_profiles(), top_k=top_k)


# ── forecast ─────────────────────────────────────────────────────────────

@app.get("/forecast", response_model=DemandForecast, tags=["forecast"])
def demand_forecast(
    trade: str | None = None,
    days: int = Query(default=7, ge=1, le=30),
    today: dt.date | None = Query(default=None, description="Override 'today' (useful for demos)"),
    _: User = Depends(require_council),
) -> DemandForecast:
    """Expected bookings per day for the coming days, and how many workers to keep on call. Council only."""
    trade = canonical_trade(trade) if trade else None
    return forecast.forecast_demand(repository.demand_dates(trade), trade=trade, horizon_days=days, today=today)


@app.get("/forecast/staffing", response_model=StaffingForecast, tags=["forecast"])
def staffing_forecast(
    trade: str = Query(description="Trade to plan for, e.g. plumbing"),
    days: int = Query(default=7, ge=1, le=30),
    area: str | None = Query(default=None, description="Optional area: matches booking addresses and workers' localities"),
    today: dt.date | None = Query(default=None, description="Override 'today' (useful for demos)"),
    _: User = Depends(require_council),
) -> StaffingForecast:
    """Forecast demand against the workers actually available: expected bookings, workers needed, available, shortage. Council only."""
    trade = canonical_trade(trade)
    demand_dates = repository.demand_dates(trade)
    workers = repository.worker_profiles(trade)
    if area:
        needle = area.strip().lower()
        with database.connection() as conn:
            demand_dates = [
                row["demand_at"] for row in conn.execute(
                    "SELECT COALESCE(scheduled_for, created_at) AS demand_at FROM bookings "
                    "WHERE trade = ? AND LOWER(COALESCE(address, '')) LIKE ?", (trade, f"%{needle}%"),
                )
            ]
            local_workers = {
                row["worker_id"] for row in conn.execute(
                    "SELECT worker_id FROM users WHERE worker_id IS NOT NULL AND LOWER(COALESCE(locality, '')) LIKE ?",
                    (f"%{needle}%",),
                )
            }
        workers = [w for w in workers if w.id in local_workers]
    demand = forecast.forecast_demand(demand_dates, trade=trade, horizon_days=days, today=today)
    return staffing.staffing_forecast(demand, workers, trade=trade, area=area.strip() if area else None)
