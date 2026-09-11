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
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from app import database, repository
from app.routers.auth import router as auth_router
from app.routers.booking_flow import router as booking_flow_router
from app.schemas import (
    Booking,
    BookingCreate,
    DemandForecast,
    Recommendation,
    ServiceRequest,
    VoiceAvailabilityRequest,
    VoiceAvailabilityResponse,
    VoiceAvailabilityResult,
    Worker,
    WorkerCreate,
)
from app.services import allocation, forecast, voice


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
def create_worker(body: WorkerCreate) -> Worker:
    return repository.create_worker(body)


@app.get("/workers", response_model=list[Worker], tags=["workers"])
def list_workers(trade: str | None = None) -> list[Worker]:
    return repository.list_workers(trade)


@app.get("/workers/{worker_id}", response_model=Worker, tags=["workers"])
def get_worker(worker_id: int) -> Worker:
    worker = repository.get_worker(worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
    return worker


@app.post("/workers/{worker_id}/availability/voice", response_model=VoiceAvailabilityResponse, tags=["workers", "voice"])
def set_availability_by_voice(worker_id: int, body: VoiceAvailabilityRequest) -> VoiceAvailabilityResponse:
    """Parse a spoken availability sentence (Hindi/English/Hinglish) and store it on the worker."""
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
def create_booking(body: BookingCreate) -> Booking:
    return repository.create_booking(body)


@app.get("/bookings", response_model=list[Booking], tags=["bookings"])
def list_bookings(status: str | None = None, trade: str | None = None) -> list[Booking]:
    return repository.list_bookings(status=status, trade=trade)


# ── allocation ───────────────────────────────────────────────────────────

@app.get("/bookings/{booking_id}/recommendations", response_model=list[Recommendation], tags=["allocation"])
def booking_recommendations(booking_id: int, top_k: int = Query(default=3, ge=1, le=20)) -> list[Recommendation]:
    """Preview the fair allocation ranking for a booking without assigning anyone."""
    booking = repository.get_booking(booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    request = ServiceRequest(
        booking_id=booking.id, trade=booking.trade, latitude=booking.latitude,
        longitude=booking.longitude, scheduled_for=booking.scheduled_for,
    )
    return allocation.recommend_workers(request, repository.worker_profiles(), top_k=top_k)


@app.post("/allocation/recommend", response_model=list[Recommendation], tags=["allocation"])
def recommend(request: ServiceRequest, top_k: int = Query(default=3, ge=1, le=20)) -> list[Recommendation]:
    """Rank workers for an ad-hoc service request (no booking record needed)."""
    return allocation.recommend_workers(request, repository.worker_profiles(), top_k=top_k)


# ── forecast ─────────────────────────────────────────────────────────────

@app.get("/forecast", response_model=DemandForecast, tags=["forecast"])
def demand_forecast(
    trade: str | None = None,
    days: int = Query(default=7, ge=1, le=30),
    today: dt.date | None = Query(default=None, description="Override 'today' (useful for demos)"),
) -> DemandForecast:
    """Expected bookings per day for the coming days, and how many workers to keep on call."""
    return forecast.forecast_demand(repository.demand_dates(trade), trade=trade, horizon_days=days, today=today)
