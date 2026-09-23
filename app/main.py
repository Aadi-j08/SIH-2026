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

import os

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app import database, events, ownership, repository
from app.auth import User, require_council, require_customer, require_user, require_worker
from app.routers.auth import router as auth_router
from app.routers.assistant import router as assistant_router
from app.routers.booking_flow import router as booking_flow_router
from app.routers.feedback import router as feedback_router
from app.routers.kaam import router as kaam_router
from app.routers.pricing import router as pricing_router
from app.routers.sabha import router as sabha_router
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
import os
import threading
from app.services import allocation, booking_flow, forecast, staffing, voice
from app.services.demand_forecast import forecaster
from app.services.dispute_advisor import analyze_payment_discrepancy
from app.services.ledger import generate_upi_qr_data
from app.services.worker_allocation import match_batch_jobs
from app.trades import canonical_trade

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sahakarsetu")

# In production, disable the interactive API docs and OpenAPI schema to keep
# internal endpoints out of public view. Set SAHAKARSETU_ENV=production on Render.
_IS_PROD = os.environ.get("SAHAKARSETU_ENV", "development").strip().lower() == "production"
_DOCS_URL = None if _IS_PROD else "/docs"
_REDOC_URL = None if _IS_PROD else "/redoc"


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="SahakarSetu",
    version="0.1.0",
    description="Fair work allocation, voice availability and demand forecasting for a workers' cooperative.",
    lifespan=lifespan,
    docs_url=_DOCS_URL,
    redoc_url=_REDOC_URL,
)


@app.middleware("http")
async def _hide_docs_in_production(request: Request, call_next):
    if _IS_PROD and request.url.path in ("/openapi.json", "/docs", "/redoc"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return await call_next(request)
app.include_router(auth_router)
app.include_router(assistant_router)
app.include_router(booking_flow_router)
app.include_router(feedback_router)
app.include_router(kaam_router)
app.include_router(sabha_router)
app.include_router(pricing_router)
app.include_router(events.router)
app.add_middleware(events.PublishChanges)

# Cross-origin SPA (Cloudflare Pages → this API). Comma-separated origins, e.g.
# https://sahakarsetu-frontend.pages.dev,http://127.0.0.1:5173
# Hard-coded fallback origins cover the known Pages deployment so the app keeps
# working even if SAHAKARSETU_CORS_ORIGINS is not yet synced on the host.
_KNOWN_PAGES_ORIGINS = ("https://sahakarsetu-frontend.pages.dev",)
_cors = list(dict.fromkeys(
    [o.strip() for o in os.environ.get("SAHAKARSETU_CORS_ORIGINS", "").split(",") if o.strip()]
    + list(_KNOWN_PAGES_ORIGINS)
))
if _cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


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
    response = {"name": "SahakarSetu", "status": "ok", "app": "/app/"}
    if not _IS_PROD:
        response["docs"] = "/docs"
    return response


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
    if not parsed.can_save:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "The availability was not understood confidently enough. Please say the day and time again.",
                "parsed": parsed.model_dump(mode="json"),
            },
        )
    if parsed.requires_confirmation and not body.confirmed:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Please confirm the interpreted availability before saving it.",
                "confirmation_message": parsed.confirmation_message,
                "parsed": parsed.model_dump(mode="json"),
            },
        )
    worker = repository.set_worker_availability(worker_id, parsed.windows, replace=body.replace)
    return VoiceAvailabilityResponse(parsed=parsed, worker=worker)


@app.post("/voice/parse", response_model=VoiceAvailabilityResult, tags=["voice"])
def parse_voice(body: VoiceAvailabilityRequest) -> VoiceAvailabilityResult:
    """Dry run of the voice parser: see what a transcript would be understood as, without saving."""
    return voice.parse_availability(body.transcript, body.reference_date)


def _auto_assign_asap(booking_id: int) -> None:
    try:
        with database.connection() as conn:
            booking_flow.assign_booking(conn, booking_id)
        events.bus.publish("bookings", "assigned", booking_id=booking_id)
        log.info("booking %s automatically matched for ASAP", booking_id)
    except Exception as e:
        log.info("auto-assign for ASAP booking %s deferred: %s", booking_id, e)


@app.post("/bookings", response_model=Booking, status_code=201, tags=["bookings"])
def create_booking(body: BookingCreate, user: User = Depends(require_customer)) -> Booking:
    """Place a booking. It belongs to the signed-in customer (or to the council member placing it on a household's behalf)."""
    booking = repository.create_booking(body)
    ownership.attach_customer(booking.id, user)
    log.info("booking %s (%s) placed by %s #%s", booking.id, booking.trade, user.access_role, user.id)
    if body.scheduled_for is None and not os.environ.get("PYTEST_CURRENT_TEST"):
        threading.Timer(2.0, _auto_assign_asap, args=[booking.id]).start()
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


@app.post("/allocation/batch-dispatch", tags=["allocation"])
def batch_dispatch(
    max_distance_km: float = Query(default=15.0, ge=1.0, le=50.0),
    _: User = Depends(require_council),
) -> dict:
    """Solves optimal fair bipartite matching between all pending bookings and available workers. Council only."""
    # Fetch pending bookings and active worker profiles
    with database.connection() as conn:
        raw_bookings = conn.execute(
            "SELECT id, customer_name, trade, latitude, longitude, address FROM bookings WHERE status = 'pending'"
        ).fetchall()
        raw_workers = conn.execute(
            "SELECT id, name, trade, latitude, longitude, jobs_this_week, rating, status FROM workers WHERE status = 'active'"
        ).fetchall()

    bookings_list = [dict(r) for r in raw_bookings]
    workers_list = [dict(r) for r in raw_workers]
    return match_batch_jobs(bookings_list, workers_list, max_distance_km=max_distance_km)


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


@app.get("/forecast/ml", tags=["forecast"])
def demand_forecast_ml(
    trade: str = Query(default="general", description="Trade category"),
    ward_id: str = Query(default="1", description="Ward identifier or locality name"),
    _: User = Depends(require_council),
) -> dict:
    """ML-powered 7-day demand and fair-price band forecast using scikit-learn Ridge regression. Council only."""
    return forecaster.predict_7_day_demand(trade=trade, ward_id=ward_id)


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


# ── payment split & dispute reporting ───────────────────────────────────

class PaymentMismatchRequest(BaseModel):
    booking_id: int
    customer_paid_rupees: float
    worker_reported_rupees: float
    standard_rate_rupees: float = 400.0
    materials_rupees: float = 0.0
    customer_notes: str | None = None


@app.get("/payments/{booking_id}/upi-qr", tags=["payments"])
def get_payment_upi_qr(
    booking_id: int,
    amount: float | None = Query(default=None, description="Optional bill amount in rupees"),
    user: User = Depends(require_user),
) -> dict:
    """Generates NPCI-compliant dynamic UPI QR payload and transparent 85/10/5 split metadata."""
    final_amount = amount
    if final_amount is None:
        with database.connection() as conn:
            row = conn.execute(
                "SELECT agreed_amount_rupees, proposed_amount_rupees FROM settlements WHERE booking_id = ?",
                (booking_id,),
            ).fetchone()
            if row:
                final_amount = float(row["agreed_amount_rupees"] or row["proposed_amount_rupees"] or 450.0)
            else:
                final_amount = 450.0
    return generate_upi_qr_data(booking_id=booking_id, total_rupees=final_amount)


@app.post("/disputes/report-mismatch", tags=["disputes"])
def report_payment_mismatch(
    body: PaymentMismatchRequest,
    user: User = Depends(require_user),
) -> dict:
    """Audits payment discrepancies (cash bypass / rate card deviations) and alerts cooperative council."""
    return analyze_payment_discrepancy(
        booking_id=body.booking_id,
        customer_paid_rupees=body.customer_paid_rupees,
        worker_reported_rupees=body.worker_reported_rupees,
        standard_rate_rupees=body.standard_rate_rupees,
        materials_rupees=body.materials_rupees,
        customer_notes=body.customer_notes,
    )
