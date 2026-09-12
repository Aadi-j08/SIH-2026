"""
Fair allocation engine.

Ranks cooperative workers for a service request. Unlike a marketplace that
always sends the job to the highest-rated or nearest worker, this engine
gives real weight to *fairness* (who has had the fewest jobs this week), so
work is spread across the cooperative and new members get a chance.

    recommend_workers(request, workers, top_k=3) -> [Recommendation, ...]

Hard filters (a worker is skipped entirely):
  - trade does not match the request
  - farther than request.max_distance_km
  - worker declared themselves busy for the requested slot

Soft factors, each scored 0..1 and combined with WEIGHTS:
  proximity     1 at the customer's door, 0 at max_distance_km
  fairness      1 for the fewest jobs this week in the pool, 0 for the most
  rating        (rating - 1) / 4; unrated workers get a neutral 0.5
  availability  1 if the worker said they are free then, 0.7 if unknown

Every recommendation carries its score breakdown and a plain-language
explanation so an admin (or the worker) can see why the choice was made.
"""
from __future__ import annotations

import math
from datetime import datetime

from app.schemas import AvailabilityWindow, Recommendation, ServiceRequest, WorkerProfile

WEIGHTS: dict[str, float] = {
    "proximity": 0.30,
    "fairness": 0.35,
    "rating": 0.20,
    "availability": 0.15,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Allocation weights must add up to 1"

NEUTRAL_RATING_SCORE = 0.5          # worker with no ratings yet
UNKNOWN_AVAILABILITY_SCORE = 0.7    # worker never declared availability for that slot
EARTH_RADIUS_KM = 6371.0


# ── helpers ──────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def normalise_trade(trade: str) -> str:
    return trade.strip().lower()


def _minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _applies(window: AvailabilityWindow, when: datetime) -> bool:
    if window.date is not None:
        return window.date == when.date()
    if window.weekday is not None:
        return window.weekday == when.weekday()
    return True  # recurs every day


def _covers(window: AvailabilityWindow, when: datetime) -> bool:
    minute = when.hour * 60 + when.minute
    return _minutes(window.start) <= minute <= _minutes(window.end)


def availability_status(windows: list[AvailabilityWindow], when: datetime | None) -> str:
    """'available', 'unavailable' or 'unknown' for the requested time.

    A declared busy window wins over a declared free one. If the worker
    declared windows for that day but none cover the slot, they are treated
    as unavailable; if they declared nothing for that day, it is unknown.
    """
    if when is None or not windows:
        return "unknown"
    applicable = [w for w in windows if _applies(w, when)]
    if not applicable:
        return "unknown"
    if any(not w.available and _covers(w, when) for w in applicable):
        return "unavailable"
    if any(w.available and _covers(w, when) for w in applicable):
        return "available"
    return "unavailable"


def rating_score(rating: float | None) -> float:
    if rating is None:
        return NEUTRAL_RATING_SCORE
    return round(min(max((rating - 1) / 4, 0.0), 1.0), 4)


# ── engine ───────────────────────────────────────────────────────────────

def recommend_workers(
    request: ServiceRequest,
    workers: list[WorkerProfile],
    top_k: int = 3,
) -> list[Recommendation]:
    """Return up to top_k workers for the request, best first.

    Returns an empty list when nobody is eligible; it never raises for an
    empty pool so callers can turn that into a clean 'no worker available'.
    """
    wanted = normalise_trade(request.trade)
    candidates: list[tuple[WorkerProfile, float, str]] = []
    for worker in workers:
        if normalise_trade(worker.trade) != wanted:
            continue
        distance = haversine_km(request.latitude, request.longitude, worker.latitude, worker.longitude)
        if distance > request.max_distance_km:
            continue
        status = availability_status(worker.availability, request.scheduled_for)
        if status == "unavailable":
            continue
        candidates.append((worker, distance, status))

    if not candidates:
        return []

    jobs = [worker.jobs_this_week for worker, _, _ in candidates]
    fewest, most = min(jobs), max(jobs)

    scored: list[tuple[Recommendation, WorkerProfile]] = []
    for worker, distance, status in candidates:
        breakdown = {
            "proximity": round(max(0.0, 1 - distance / request.max_distance_km), 4),
            "fairness": 1.0 if most == fewest else round(1 - (worker.jobs_this_week - fewest) / (most - fewest), 4),
            "rating": rating_score(worker.rating),
            "availability": 1.0 if status == "available" else UNKNOWN_AVAILABILITY_SCORE,
        }
        score = round(sum(WEIGHTS[factor] * value for factor, value in breakdown.items()), 4)
        scored.append((
            Recommendation(
                rank=0,
                worker_id=worker.id,
                worker_name=worker.name,
                distance_km=round(distance, 2),
                score=score,
                score_breakdown=breakdown,
                explanation=_explain(worker, distance, status, fewest),
                why_selected=_why_selected(worker, distance, status, fewest, request.max_distance_km),
            ),
            worker,
        ))

    # Ties go to whoever has had less work, then whoever is nearer.
    scored.sort(key=lambda pair: (-pair[0].score, pair[1].jobs_this_week, pair[0].distance_km, pair[1].id))
    ranked = []
    for position, (recommendation, _) in enumerate(scored[:top_k], start=1):
        ranked.append(recommendation.model_copy(update={"rank": position}))
    return ranked


def _explain(worker: WorkerProfile, distance: float, status: str, fewest_jobs: int) -> str:
    parts = [f"{worker.name or 'Worker ' + str(worker.id)}: {distance:.1f} km from the customer"]
    if worker.jobs_this_week == fewest_jobs:
        parts.append(f"{worker.jobs_this_week} jobs this week (fewest in the pool, so fairness favours them)")
    else:
        parts.append(f"{worker.jobs_this_week} jobs this week")
    parts.append(f"rated {worker.rating:.1f}/5" if worker.rating is not None else "no ratings yet")
    parts.append("declared available for this slot" if status == "available" else "availability not declared for this slot")
    return "; ".join(parts) + "."


def _why_selected(
    worker: WorkerProfile,
    distance: float,
    status: str,
    fewest_jobs: int,
    max_distance_km: float,
) -> list[str]:
    """Return short evidence statements suitable for a council dashboard."""
    reasons = [f"within the {max_distance_km:g} km service radius ({distance:.1f} km away)"]
    if worker.jobs_this_week == fewest_jobs:
        reasons.append(f"fewest jobs this week ({worker.jobs_this_week})")
    if worker.rating is not None:
        reasons.append(f"rated {worker.rating:.1f}/5")
    else:
        reasons.append("new worker with no ratings yet")
    reasons.append("declared available for the requested slot" if status == "available" else "no conflicting availability declared")
    return reasons
