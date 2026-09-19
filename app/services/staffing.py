"""
Staffing check: does the cooperative have enough workers for the demand ahead?

Puts two existing things side by side without changing either:
  - the demand forecast (app/services/forecast.py): expected bookings and
    workers needed per day, and
  - workers' declared availability (app/services/allocation.py's
    availability_status): who is not declared busy on that day.

A worker counts as available on a day if, at the working-day reference
time, their declared windows say "available" or say nothing ("unknown");
a declared "unavailable" removes them. That mirrors what the allocation
engine would do when a booking for that day arrives.
"""
from __future__ import annotations

import datetime as dt

from app.schemas import DemandForecast, StaffingDay, StaffingForecast, WorkerProfile
from app.services.allocation import availability_status
from app.trades import canonical_trade

REFERENCE_HOUR = 10   # a typical morning slot; availability is judged at this time of day


def available_workers_on(workers: list[WorkerProfile], day: dt.date, trade: str) -> int:
    wanted = canonical_trade(trade)
    when = dt.datetime(day.year, day.month, day.day, REFERENCE_HOUR)
    return sum(
        1 for w in workers
        if canonical_trade(w.trade) == wanted and availability_status(w.availability, when) != "unavailable"
    )


def staffing_forecast(
    forecast: DemandForecast,
    workers: list[WorkerProfile],
    *,
    trade: str,
    area: str | None = None,
) -> StaffingForecast:
    """Compare each forecast day's workers_needed with the workers available that day."""
    days: list[StaffingDay] = []
    for point in forecast.points:
        available = available_workers_on(workers, point.date, trade)
        days.append(StaffingDay(
            date=point.date,
            weekday=point.weekday,
            expected_bookings=point.expected_bookings,
            workers_needed=point.workers_needed,
            available_workers=available,
            shortage=max(0, point.workers_needed - available),
            confidence=point.confidence,
            forecast_jobs=point.expected_bookings,
            explanation=(
                f"Forecast requires {point.workers_needed} worker{'s' if point.workers_needed != 1 else ''}; "
                f"{available} active worker{'s are' if available != 1 else ' is'} available."
            ),
        ))

    # Headline = the day that needs attention most: biggest shortage, then biggest need.
    peak = max(days, key=lambda d: (d.shortage, d.workers_needed, -d.date.toordinal()), default=None)
    trade_word = canonical_trade(trade)
    if peak is None:
        recommendation = "No forecast days requested."
    elif peak.shortage > 0:
        plural = "s" if peak.shortage > 1 else ""
        recommendation = (
            f"Request availability from {peak.shortage} additional {trade_word} worker{plural} "
            f"for {peak.weekday} {peak.date.isoformat()}"
        )
    elif peak.workers_needed == 0:
        recommendation = f"No {trade_word} bookings expected in the next {forecast.horizon_days} days."
    else:
        recommendation = f"Enough {trade_word} workers are available for the next {forecast.horizon_days} days."

    return StaffingForecast(
        trade=trade_word,
        area=area,
        horizon_days=forecast.horizon_days,
        peak_day=peak.date if peak else None,
        expected_bookings=peak.expected_bookings if peak else 0.0,
        workers_needed=peak.workers_needed if peak else 0,
        available_workers=peak.available_workers if peak else 0,
        shortage=peak.shortage if peak else 0,
        recommendation=recommendation,
        days=days,
        confidence=peak.confidence if peak else 0.35,
        explanation=(
            f"{trade_word} staffing compares the explainable demand baseline with active workers "
            f"who are not declared busy on the peak day."
        ),
    )
