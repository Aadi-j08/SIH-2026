"""
Pricing — the community rate card and the price agreed at the end of a job.

  GET  /rates                                anyone signed in: the card, every trade
  GET  /rates/quote?trade=&hours=&materials= anyone signed in: what the card says a job should cost
  PUT  /rates/{trade}                        council: change the card (after a general-body resolution)
  GET  /settlements?status=                  council: every settlement, open ones first
  GET  /bookings/{id}/settlement             the customer, the worker, council
  POST /bookings/{id}/settlement             the assigned worker (council on their behalf): propose
  POST /bookings/{id}/settlement/respond     customer: agree / counter / dispute · worker: agree / dispute
  POST /bookings/{id}/settlement/resolve     council: fix the amount, close the dispute
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app import rates, settlements
from app.auth import User, require_council, require_user, require_worker
from app.database import connection

router = APIRouter(tags=["pricing"])


def _call(fn, *args):
    try:
        return fn(*args)
    except settlements.SettlementError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


# ── rate card ────────────────────────────────────────────────────────────

@router.get("/rates", response_model=list[rates.Rate])
def rate_card(_: User = Depends(require_user)) -> list[rates.Rate]:
    return rates.list_rates()


@router.get("/rates/quote", response_model=rates.Quote)
def rate_quote(
    trade: str = Query(min_length=1),
    hours: float = Query(default=1.0, gt=0, le=24),
    materials: float = Query(default=0.0, ge=0, le=1_000_000),
    _: User = Depends(require_user),
) -> rates.Quote:
    with connection() as conn:
        return rates.quote(conn, trade, hours, materials)


@router.put("/rates/{trade}", response_model=rates.Rate)
def edit_rate(trade: str, body: rates.RateUpdate, _: User = Depends(require_council)) -> rates.Rate:
    return rates.update_rate(trade, body)


# ── settlement ───────────────────────────────────────────────────────────

@router.get("/settlements", response_model=list[settlements.Settlement])
def list_settlements(
    status: str | None = Query(default=None, pattern="^(proposed|countered|agreed|disputed|open)$"),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_council),
) -> list[settlements.Settlement]:
    """Every price on the table or agreed; `open` = proposed + countered + disputed."""
    return settlements.list_all(status, limit)


@router.get("/bookings/{booking_id}/settlement", response_model=settlements.Settlement | None)
def get_settlement(booking_id: int, user: User = Depends(require_user)) -> settlements.Settlement | None:
    """The price on the table for this job, or null if the worker has not proposed one yet."""
    return _call(settlements.get, user, booking_id)


@router.post("/bookings/{booking_id}/settlement", response_model=settlements.Settlement, status_code=201)
def propose_settlement(booking_id: int, body: settlements.Propose, user: User = Depends(require_worker)) -> settlements.Settlement:
    """Job done: the worker says hours, materials and a note; the card prices it and the customer is asked to agree."""
    return _call(settlements.propose, user, booking_id, body)


@router.post("/bookings/{booking_id}/settlement/respond", response_model=settlements.Settlement)
def respond_settlement(booking_id: int, body: settlements.Respond, user: User = Depends(require_user)) -> settlements.Settlement:
    """Agree (the job completes and the ledger runs), counter within the fair band, or ask the Sabha to decide."""
    return _call(settlements.respond, user, booking_id, body)


@router.post("/bookings/{booking_id}/settlement/resolve", response_model=settlements.Settlement)
def resolve_settlement(booking_id: int, body: settlements.Resolve, user: User = Depends(require_council)) -> settlements.Settlement:
    return _call(settlements.resolve, user, booking_id, body)
