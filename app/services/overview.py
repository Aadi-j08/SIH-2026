"""
The Sabha overview: one call that answers the council's questions —
what work is coming in, who can do it, is it shared fairly, where the money
goes, is the cooperative healthy, and does anything need a hand.

Everything is computed from the tables that already exist (bookings,
assignments, payment_ledger, booking_ratings, workers, users, disputes)
plus the two policies on the cooperative row: the weekly job limit and the
fund allocation. The matching suggestions reuse the allocation engine as-is.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from app import disputes as disputes_mod
from app.cooperative import Cooperative, get_cooperative
from app.schemas import ServiceRequest, WorkerProfile
from app.services import allocation, forecast as forecast_mod, staffing
from app.services.booking_flow import gini, paise_to_rupees
from app.trades import CANONICAL_TRADES, canonical_trade

ACTIVE_WINDOW_DAYS = 30           # a worker with an assignment in this window counts as active
IST = dt.timedelta(hours=5, minutes=30)
REFERENCE_HOUR = 10               # "available today" is judged at this local hour, like the staffing forecast
STALE_PENDING_HOURS = 2           # a demand unassigned longer than this needs attention
NEAR_LIMIT_MARGIN = 1             # jobs_this_week >= limit - margin → "nearing weekly limit"


# ── response models ──────────────────────────────────────────────────────

class CoopSummary(BaseModel):
    name: str
    short_name: str
    verified: bool
    members: int
    active_workers: int
    categories: int


class DemandMetrics(BaseModel):
    active: int
    unassigned: int
    ongoing: int
    completed_today: int


class WorkerMetrics(BaseModel):
    active: int
    registered: int
    available_now: int


class EarningsMetrics(BaseModel):
    this_month_rupees: float
    last_month_rupees: float
    change_pct: float | None = Field(description="vs the same days of last month; None when there were no earnings then")


class FairnessMetrics(BaseModel):
    index: int = Field(ge=0, le=100)
    workload: int = Field(ge=0, le=100, description="1 - Gini of jobs per active worker over the last 30 days")
    pay: int = Field(ge=0, le=100, description="1 - Gini of this month's earnings among earners")
    allocation: int = Field(ge=0, le=100, description="share of registered workers who got work in the last 30 days")


class FundMetrics(BaseModel):
    total_rupees: float
    this_month_rupees: float
    allocation: dict[str, int]


class Metrics(BaseModel):
    demands: DemandMetrics
    workers: WorkerMetrics
    earnings: EarningsMetrics
    fairness: FairnessMetrics
    fund: FundMetrics


class AttentionItem(BaseModel):
    level: str = Field(description="red / amber / green")
    kind: str = Field(description="assign / disputes / workload / opportunity")
    count: int
    text: str
    action: str
    trade: str | None = None


class TradeRow(BaseModel):
    trade: str
    demand: int = Field(description="pending + assigned bookings")
    unassigned: int
    ongoing: int
    available_workers: int
    status: str = Field(description="good / moderate / needs_workers / idle")


class Suggestion(BaseModel):
    worker_id: int
    name: str
    distance_km: float
    rating: float | None
    availability: str
    jobs_this_week: int
    score: float
    explanation: str


class MatchingGroup(BaseModel):
    trade: str
    unassigned: int
    booking_id: int = Field(description="the oldest unassigned booking of this trade, which the suggestions are for")
    booking_age_minutes: int
    suggestions: list[Suggestion]


class WorkloadRow(BaseModel):
    worker_id: int
    name: str
    trade: str
    jobs_this_week: int
    limit: int
    pct: int
    flag: str | None = Field(description="overloaded / under_utilised / None")


class Network(BaseModel):
    registered: int
    active: int
    available: int
    offline: int
    limit: int
    workload: list[WorkloadRow]


class Performance(BaseModel):
    jobs_completed: int
    workers_benefited: int
    avg_worker_earnings_month_rupees: float
    repeat_customers_pct: float | None
    disputes_resolved_pct: float | None
    avg_response_minutes: float | None


class DisputeSummary(BaseModel):
    open: int
    resolved: int
    resolution_rate: float | None
    recent: list[disputes_mod.Dispute]


class ForecastInsight(BaseModel):
    trade: str | None
    peak_day: dt.date | None
    peak_weekday: str | None
    expected_bookings: float
    workers_needed: int
    available_workers: int
    shortage: int
    text: str


class Overview(BaseModel):
    generated_at: str
    cooperative: CoopSummary
    profile: Cooperative
    metrics: Metrics
    attention: list[AttentionItem]
    trades: list[TradeRow]
    matching: list[MatchingGroup]
    network: Network
    performance: Performance
    disputes: DisputeSummary
    forecast_insight: ForecastInsight


# ── helpers ──────────────────────────────────────────────────────────────

def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def _stamp(when: dt.datetime) -> str:
    """SQLite CURRENT_TIMESTAMP spelling."""
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _parse(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    text = value.replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _month_start(when: dt.datetime) -> dt.datetime:
    return when.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _profiles(conn: sqlite3.Connection) -> list[WorkerProfile]:
    import json
    profiles = []
    for row in conn.execute("SELECT * FROM workers ORDER BY id"):
        data = dict(row)
        data["availability"] = json.loads(data.get("availability") or "[]")
        profiles.append(WorkerProfile.model_validate(data))
    return profiles


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def _trade_status(demand: int, unassigned: int, available: int) -> str:
    if demand == 0:
        return "idle"
    if available == 0 or available < unassigned:
        return "needs_workers"
    if available < demand:
        return "moderate"
    return "good"


# ── the overview ─────────────────────────────────────────────────────────

def overview(conn: sqlite3.Connection, now: dt.datetime | None = None) -> Overview:
    now = now or _utcnow()
    profile = get_cooperative(conn)
    limit = profile.weekly_job_limit
    this_month, last_month = _month_start(now), _month_start(_month_start(now) - dt.timedelta(days=1))
    last_month_to_date = last_month + (now - this_month)          # the same stretch of last month, for a fair comparison
    today = (now + IST).date()
    reference = dt.datetime.combine(today, dt.time(REFERENCE_HOUR))   # local time the availability windows are written in
    active_since = _stamp(now - dt.timedelta(days=ACTIVE_WINDOW_DAYS))
    have_ledger = _has_table(conn, "payment_ledger")

    # workers ----------------------------------------------------------------
    profiles = _profiles(conn)
    workers_by_id = {w.id: w for w in profiles}
    active_ids = {
        r["worker_id"] for r in conn.execute("SELECT DISTINCT worker_id FROM assignments WHERE created_at >= ?", (active_since,))
    }
    status_now = {w.id: allocation.availability_status(w.availability, reference) for w in profiles}
    available_ids = {w.id for w in profiles if status_now[w.id] != "unavailable" and w.jobs_this_week < limit}
    offline_ids = {w.id for w in profiles if status_now[w.id] == "unavailable"}
    trades_present = {canonical_trade(w.trade) for w in profiles}

    # bookings ---------------------------------------------------------------
    bookings = [dict(r) for r in conn.execute("SELECT * FROM bookings")]
    by_status: dict[str, list[dict]] = defaultdict(list)
    for b in bookings:
        by_status[b["status"]].append(b)
    pending, assigned, completed = by_status["pending"], by_status["assigned"], by_status["completed"]
    completed_today = sum(
        1 for b in completed
        if (c := _parse(b.get("completed_at"))) is not None and (c + IST).date() == today
    )

    # money ------------------------------------------------------------------
    worker_month = worker_last = fund_total = fund_month = 0
    earners_month: dict[int, int] = defaultdict(int)
    benefited: set[int] = set()
    if have_ledger:
        for r in conn.execute("SELECT party, worker_id, amount_paise, created_at FROM payment_ledger"):
            when = _parse(r["created_at"]) or now
            if r["party"] == "worker":
                benefited.add(r["worker_id"])
                if when >= this_month:
                    worker_month += r["amount_paise"]
                    earners_month[r["worker_id"]] += r["amount_paise"]
                elif last_month <= when < last_month_to_date:
                    worker_last += r["amount_paise"]
            elif r["party"] == "welfare_fund":
                fund_total += r["amount_paise"]
                if when >= this_month:
                    fund_month += r["amount_paise"]
    change_pct = round((worker_month - worker_last) / worker_last * 100, 1) if worker_last else None

    # fairness ---------------------------------------------------------------
    recent_jobs = {r["worker_id"]: r["n"] for r in conn.execute(
        "SELECT worker_id, COUNT(*) AS n FROM assignments WHERE created_at >= ? GROUP BY worker_id", (active_since,))}
    workload_score = round((1 - gini([float(n) for n in recent_jobs.values()])) * 100) if recent_jobs else 100
    pay_score = round((1 - gini([float(v) for v in earners_month.values()])) * 100) if earners_month else 100
    allocation_score = round(len(active_ids) / len(profiles) * 100) if profiles else 100
    fairness = FairnessMetrics(
        index=round((workload_score + pay_score + allocation_score) / 3),
        workload=workload_score, pay=pay_score, allocation=allocation_score,
    )

    # per trade ----------------------------------------------------------------
    trade_names = list(CANONICAL_TRADES) + sorted(t for t in trades_present if t not in CANONICAL_TRADES)
    trade_rows: list[TradeRow] = []
    for trade in trade_names:
        unassigned = sum(1 for b in pending if canonical_trade(b["trade"]) == trade)
        ongoing = sum(1 for b in assigned if canonical_trade(b["trade"]) == trade)
        available = sum(1 for w in profiles if canonical_trade(w.trade) == trade and w.id in available_ids)
        if unassigned + ongoing == 0 and trade not in trades_present:
            continue
        trade_rows.append(TradeRow(
            trade=trade, demand=unassigned + ongoing, unassigned=unassigned, ongoing=ongoing,
            available_workers=available, status=_trade_status(unassigned + ongoing, unassigned, available),
        ))

    # matching suggestions: the oldest unassigned booking per trade, ranked by the engine
    matching: list[MatchingGroup] = []
    for row in trade_rows:
        if row.unassigned == 0:
            continue
        oldest = min((b for b in pending if canonical_trade(b["trade"]) == row.trade), key=lambda b: (b["created_at"], b["id"]))
        request = ServiceRequest(
            booking_id=oldest["id"], trade=row.trade, latitude=oldest["latitude"], longitude=oldest["longitude"],
            scheduled_for=_parse(oldest.get("scheduled_for")),
        )
        pool = [w for w in profiles if canonical_trade(w.trade) == row.trade]
        recs = allocation.recommend_workers(request, pool, top_k=3)
        when = request.scheduled_for or reference
        suggestions = [
            Suggestion(
                worker_id=r.worker_id, name=r.worker_name, distance_km=round(r.distance_km, 1),
                rating=workers_by_id[r.worker_id].rating, jobs_this_week=workers_by_id[r.worker_id].jobs_this_week,
                availability=allocation.availability_status(workers_by_id[r.worker_id].availability, when),
                score=round(r.score, 2), explanation=r.explanation,
            )
            for r in recs
        ]
        age = _parse(oldest["created_at"])
        matching.append(MatchingGroup(
            trade=row.trade, unassigned=row.unassigned, booking_id=oldest["id"],
            booking_age_minutes=int((now - age).total_seconds() // 60) if age else 0, suggestions=suggestions,
        ))

    # attention ----------------------------------------------------------------
    stale_cutoff = now - dt.timedelta(hours=STALE_PENDING_HOURS)
    stale = [b for b in pending if (_parse(b["created_at"]) or now) <= stale_cutoff]
    dispute_stats = disputes_mod.dispute_stats(conn)
    near_limit = [w for w in profiles if w.jobs_this_week >= max(1, limit - NEAR_LIMIT_MARGIN)]
    attention: list[AttentionItem] = []
    if stale:
        hours = STALE_PENDING_HOURS
        attention.append(AttentionItem(
            level="red", kind="assign", count=len(stale),
            text=f"{len(stale)} demand{'s' if len(stale) != 1 else ''} unassigned for more than {hours} hours", action="Assign workers",
        ))
    if dispute_stats.open:
        attention.append(AttentionItem(
            level="amber", kind="disputes", count=dispute_stats.open,
            text=f"{dispute_stats.open} dispute{'s' if dispute_stats.open != 1 else ''} pending review", action="Review",
        ))
    if near_limit:
        attention.append(AttentionItem(
            level="amber", kind="workload", count=len(near_limit),
            text=f"{len(near_limit)} worker{'s' if len(near_limit) != 1 else ''} nearing the weekly workload limit ({limit} jobs)", action="Redistribute",
        ))
    busiest = max(trade_rows, key=lambda t: (t.unassigned, t.available_workers), default=None)
    if busiest and busiest.available_workers:
        attention.append(AttentionItem(
            level="green", kind="opportunity", count=busiest.available_workers, trade=busiest.trade,
            text=f"{busiest.available_workers} worker{'s' if busiest.available_workers != 1 else ''} available for {busiest.trade} jobs",
            action="View opportunities",
        ))

    # network ------------------------------------------------------------------
    workload = sorted(profiles, key=lambda w: (-w.jobs_this_week, w.name))
    workload_rows = []
    for w in workload[:8]:
        pct = min(100, round(w.jobs_this_week / limit * 100))
        flag = "overloaded" if pct >= 90 else ("under_utilised" if pct <= 20 and w.id in active_ids else None)
        workload_rows.append(WorkloadRow(
            worker_id=w.id, name=w.name, trade=canonical_trade(w.trade), jobs_this_week=w.jobs_this_week,
            limit=limit, pct=pct, flag=flag,
        ))
    network = Network(
        registered=len(profiles), active=len(active_ids), available=len(available_ids), offline=len(offline_ids),
        limit=limit, workload=workload_rows,
    )

    # performance --------------------------------------------------------------
    customers = defaultdict(int)
    for b in bookings:
        if b.get("customer_user_id"):
            customers[b["customer_user_id"]] += 1
    repeat_pct = round(sum(1 for n in customers.values() if n >= 2) / len(customers) * 100, 1) if customers else None
    response_minutes: list[float] = []
    for r in conn.execute(
        "SELECT a.created_at AS assigned_at, b.created_at AS booked_at FROM assignments a JOIN bookings b ON b.id = a.booking_id "
        "WHERE a.created_at >= ?", (active_since,)
    ):
        a, b = _parse(r["assigned_at"]), _parse(r["booked_at"])
        if a and b and a >= b:
            response_minutes.append((a - b).total_seconds() / 60)
    performance = Performance(
        jobs_completed=len(completed),
        workers_benefited=len(benefited),
        avg_worker_earnings_month_rupees=paise_to_rupees(round(worker_month / len(earners_month))) if earners_month else 0.0,
        repeat_customers_pct=repeat_pct,
        disputes_resolved_pct=round(dispute_stats.resolution_rate * 100, 1) if dispute_stats.resolution_rate is not None else None,
        avg_response_minutes=round(sum(response_minutes) / len(response_minutes), 1) if response_minutes else None,
    )

    # forecast insight ---------------------------------------------------------
    insight = ForecastInsight(trade=None, peak_day=None, peak_weekday=None, expected_bookings=0, workers_needed=0,
                              available_workers=0, shortage=0, text="No bookings yet to forecast from.")
    best: tuple[int, int, Any] | None = None
    for trade in trade_names:
        dates = [r["demand_at"] for r in conn.execute(
            "SELECT COALESCE(scheduled_for, created_at) AS demand_at FROM bookings WHERE trade = ?", (trade,)
        )]
        if not dates:
            continue
        fc = forecast_mod.forecast_demand(dates, trade=trade, horizon_days=7, today=today)
        st = staffing.staffing_forecast(fc, [w for w in profiles if canonical_trade(w.trade) == trade], trade=trade)
        key = (st.shortage, st.workers_needed)
        if best is None or key > best[:2]:
            best = (st.shortage, st.workers_needed, st)
    if best is not None:
        st = best[2]
        peak = next((d for d in st.days if d.date == st.peak_day), None)
        weekday = peak.weekday if peak else None
        when = "this weekend" if weekday in ("Saturday", "Sunday") else (f"on {weekday}" if weekday else "this week")
        if st.shortage > 0:
            text = (f"High {st.trade} demand expected {when}. "
                    f"{st.shortage} additional worker{'s' if st.shortage != 1 else ''} recommended.")
        elif st.workers_needed > 0:
            text = f"{st.trade.capitalize()} peaks {when} ({st.workers_needed} workers needed); the available workforce covers it."
        else:
            text = "Workforce covers the forecast for the next 7 days."
        insight = ForecastInsight(
            trade=st.trade, peak_day=st.peak_day, peak_weekday=weekday, expected_bookings=st.expected_bookings,
            workers_needed=st.workers_needed, available_workers=st.available_workers, shortage=st.shortage, text=text,
        )

    members = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return Overview(
        generated_at=now.isoformat(timespec="seconds"),
        cooperative=CoopSummary(
            name=profile.name, short_name=profile.short_name, verified=profile.verified,
            members=members, active_workers=len(active_ids), categories=len(trades_present),
        ),
        profile=profile,
        metrics=Metrics(
            demands=DemandMetrics(active=len(pending) + len(assigned), unassigned=len(pending), ongoing=len(assigned), completed_today=completed_today),
            workers=WorkerMetrics(active=len(active_ids), registered=len(profiles), available_now=len(available_ids)),
            earnings=EarningsMetrics(this_month_rupees=paise_to_rupees(worker_month), last_month_rupees=paise_to_rupees(worker_last), change_pct=change_pct),
            fairness=fairness,
            fund=FundMetrics(total_rupees=paise_to_rupees(fund_total), this_month_rupees=paise_to_rupees(fund_month), allocation=profile.fund_allocation),
        ),
        attention=attention,
        trades=trade_rows,
        matching=matching,
        network=network,
        performance=performance,
        disputes=DisputeSummary(
            open=dispute_stats.open, resolved=dispute_stats.resolved, resolution_rate=dispute_stats.resolution_rate,
            recent=disputes_mod.list_disputes(status="open", limit=4),
        ),
        forecast_insight=insight,
    )
