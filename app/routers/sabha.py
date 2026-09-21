"""
Sabha — the cooperative's own endpoints.

  GET  /cooperative                    any signed-in user (the profile is public within the cooperative)
  PUT  /cooperative                    council
  GET  /admin/overview                 council: everything the Sabha dashboard shows, in one call
  GET  /admin/customers                council: Ghar accounts with their booking counts
  POST /allocation/auto?trade=         council: assign every unassigned booking of a trade with the engine's top pick
  POST /disputes                       customer / worker (own booking), council
  GET  /disputes                       council
  POST /disputes/{id}/resolve          council
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import disputes as disputes_mod
from app.auth import User, require_council, require_user
from app.booking_flow_db import booking_flow_connection
from app.cooperative import Cooperative, CooperativeUpdate, get_cooperative, update_cooperative
from app.database import connection
from app.services import booking_flow
from app.services.allocation_bridge import AllocationBridgeError
from app.services.overview import Overview, overview
from app.trades import canonical_trade

log = logging.getLogger("sahakarsetu.sabha")
router = APIRouter(tags=["sabha"])


# ── cooperative profile ──────────────────────────────────────────────────

@router.get("/cooperative", response_model=Cooperative)
def read_cooperative(_: User = Depends(require_user)) -> Cooperative:
    return get_cooperative()


@router.put("/cooperative", response_model=Cooperative)
def edit_cooperative(body: CooperativeUpdate, _: User = Depends(require_council)) -> Cooperative:
    return update_cooperative(body)


# ── overview ─────────────────────────────────────────────────────────────

@router.get("/admin/overview", response_model=Overview)
def admin_overview(_: User = Depends(require_council)) -> Overview:
    """Cooperative health, what needs attention, demand vs workforce, matching, fairness, fund, performance, disputes."""
    with booking_flow_connection() as conn:
        return overview(conn)


class CustomerRow(BaseModel):
    id: int
    name: str
    phone: str
    locality: str | None
    bookings: int
    completed: int
    last_booking_at: str | None
    joined_at: str | None


@router.get("/admin/customers", response_model=list[CustomerRow])
def admin_customers(_: User = Depends(require_council)) -> list[CustomerRow]:
    with connection() as conn:
        rows = conn.execute(
            """SELECT u.id, u.name, u.phone, u.locality, u.created_at AS joined_at,
                      COUNT(b.id) AS bookings,
                      SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) AS completed,
                      MAX(b.created_at) AS last_booking_at
               FROM users u LEFT JOIN bookings b ON b.customer_user_id = u.id
               WHERE u.portal = 'ghar'
               GROUP BY u.id ORDER BY bookings DESC, u.name"""
        )
        return [CustomerRow(**dict(r)) for r in rows]


# ── auto-allocation ──────────────────────────────────────────────────────

class AutoAllocation(BaseModel):
    trade: str | None
    attempted: int
    assigned: list[dict[str, Any]]
    skipped: list[dict[str, Any]]


@router.post("/allocation/auto", response_model=AutoAllocation)
def auto_allocate(
    trade: str | None = Query(default=None, description="Only this trade; omit for every unassigned booking"),
    limit: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_council),
) -> AutoAllocation:
    """Assign unassigned bookings, oldest first, each with the engine's top recommendation. Every assignment keeps its explanation."""
    trade = canonical_trade(trade) if trade else None
    with connection() as conn:
        if trade:
            rows = conn.execute("SELECT id FROM bookings WHERE status = 'pending' AND trade = ? ORDER BY created_at, id LIMIT ?", (trade, limit))
        else:
            rows = conn.execute("SELECT id FROM bookings WHERE status = 'pending' ORDER BY created_at, id LIMIT ?", (limit,))
        ids = [r["id"] for r in rows]

    assigned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for booking_id in ids:
        try:
            with booking_flow_connection() as conn:
                result = booking_flow.assign_booking(conn, booking_id)
            assigned.append({
                "booking_id": booking_id, "worker_id": result["worker"]["id"], "worker_name": result["worker"].get("name"),
                "score": result["score"], "explanation": result["explanation"],
            })
        except booking_flow.BookingFlowError as exc:
            skipped.append({"booking_id": booking_id, "reason": str(exc)})
        except AllocationBridgeError as exc:
            log.error("auto-allocation: engine failed for booking %s: %s", booking_id, exc)
            skipped.append({"booking_id": booking_id, "reason": "The allocation engine could not process this booking."})
    return AutoAllocation(trade=trade, attempted=len(ids), assigned=assigned, skipped=skipped)


# ── disputes ─────────────────────────────────────────────────────────────

def _dispute_call(fn, *args):
    try:
        return fn(*args)
    except disputes_mod.DisputeError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


@router.post("/disputes", response_model=disputes_mod.Dispute, status_code=201)
def raise_dispute(body: disputes_mod.DisputeCreate, user: User = Depends(require_user)) -> disputes_mod.Dispute:
    """A customer or worker raises a dispute on a booking they are party to (council may raise one on any booking)."""
    return _dispute_call(disputes_mod.create_dispute, user, body)


@router.get("/disputes", response_model=list[disputes_mod.Dispute])
def list_disputes(
    status: str | None = Query(default=None, pattern="^(open|resolved)$"),
    _: User = Depends(require_council),
) -> list[disputes_mod.Dispute]:
    return disputes_mod.list_disputes(status)


@router.post("/disputes/{dispute_id}/resolve", response_model=disputes_mod.Dispute)
def resolve_dispute(dispute_id: int, body: disputes_mod.DisputeResolve, _: User = Depends(require_council)) -> disputes_mod.Dispute:
    return _dispute_call(disputes_mod.resolve_dispute, dispute_id, body)


from app.services.dispute_advisor import analyze_sentiment, generate_ai_dispute_recommendation


class ReviewSentimentRequest(BaseModel):
    text: str


@router.get("/disputes/{dispute_id}/ai-recommendation")
def dispute_ai_recommendation(dispute_id: int, _: User = Depends(require_council)) -> dict:
    """Generates AI-powered fair midpoint settlement calculation and diplomatic resolution note."""
    disputes_list = disputes_mod.list_disputes()
    match = next((d for d in disputes_list if d.id == dispute_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return generate_ai_dispute_recommendation(match.model_dump())


@router.post("/reviews/analyze-sentiment")
def review_sentiment_analysis(body: ReviewSentimentRequest, _: User = Depends(require_council)) -> dict:
    """Evaluates customer/worker feedback sentiment and flags toxic grievances for council mediation."""
    return analyze_sentiment(body.text)
