"""
Demand forecast.

Expected bookings per day for the next N days (optionally for one trade), so
the cooperative can plan how many workers to keep on call. A weekday-seasonal
moving average over recent booking history: pure Python, no numpy, no
external service, and every number is explainable to an admin.

    forecast_demand(demand_dates, horizon_days=7, today=date(2026, 9, 11))

`demand_dates` are the days demand landed on (a booking's scheduled_for, or
created_at when no slot was requested). Past dates are history, dates from
today onwards are bookings already on the calendar for the horizon.

Method
  1. Daily counts over the last `history_weeks` weeks, ending yesterday.
  2. level = recency-weighted daily mean (the last 7 days count 60%).
  3. weekday factor = mean(count on that weekday) / mean(all days), shrunk
     toward 1 when there are few observations, so one quiet Sunday does not
     zero out every future Sunday.
  4. expected = level x factor, never below what is already booked that day.
  5. 80% band = expected +/- 1.28 * sqrt(expected)  (Poisson approximation).
  6. workers_needed = ceil(upper / jobs_per_worker_per_day): plan for the busy case.
"""
from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from app.schemas import DemandForecast, ForecastPoint

SHRINKAGE = 2.0          # pseudo-observations pulling each weekday factor toward 1.0
Z_80 = 1.28              # 80% interval half-width in standard deviations
RECENT_WEIGHT = 0.6      # weight of the last 7 days in the level estimate
DEFAULT_JOBS_PER_WORKER_PER_DAY = 3


def _as_date(value: datetime | date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def daily_counts(demand_dates: Iterable[date], first: date, days: int) -> list[int]:
    """Bookings per day for `days` days starting at `first`; dates outside are ignored."""
    counts = [0] * days
    for day in demand_dates:
        offset = (day - first).days
        if 0 <= offset < days:
            counts[offset] += 1
    return counts


def weekday_factors(counts: list[int], first: date) -> dict[int, float]:
    """Seasonality per weekday (0 = Monday), normalised to average 1.0."""
    overall = sum(counts) / len(counts) if counts else 0.0
    samples: dict[int, list[int]] = {weekday: [] for weekday in range(7)}
    for offset, count in enumerate(counts):
        samples[(first + timedelta(days=offset)).weekday()].append(count)
    factors = {}
    for weekday, values in samples.items():
        n = len(values)
        raw = (sum(values) / n) / overall if n and overall > 0 else 1.0
        factors[weekday] = (n * raw + SHRINKAGE) / (n + SHRINKAGE)
    mean_factor = sum(factors.values()) / 7
    return {weekday: factor / mean_factor for weekday, factor in factors.items()}


def forecast_demand(
    demand_dates: Iterable[datetime | date | str],
    *,
    trade: str | None = None,
    horizon_days: int = 7,
    today: date | None = None,
    history_weeks: int = 4,
    jobs_per_worker_per_day: int = DEFAULT_JOBS_PER_WORKER_PER_DAY,
) -> DemandForecast:
    today = today or date.today()
    history_days = history_weeks * 7
    first = today - timedelta(days=history_days)
    dates = [_as_date(value) for value in demand_dates]

    counts = daily_counts(dates, first, history_days)
    already_booked = daily_counts(dates, today, horizon_days)
    history_bookings = sum(counts)

    if history_bookings == 0:
        level, factors, method = 0.0, {weekday: 1.0 for weekday in range(7)}, "no booking history yet"
        confidence = 0.35
    else:
        overall = history_bookings / history_days
        recent = counts[-7:]
        recent_mean = sum(recent) / len(recent)
        level = RECENT_WEIGHT * recent_mean + (1 - RECENT_WEIGHT) * overall
        factors = weekday_factors(counts, first)
        method = f"weekday-seasonal moving average over {history_weeks} weeks"
        confidence = round(min(0.9, 0.55 + min(0.3, history_bookings / 100)), 2)

    points = []
    for offset in range(horizon_days):
        day = today + timedelta(days=offset)
        booked = already_booked[offset]
        expected = max(level * factors[day.weekday()], float(booked))
        band = Z_80 * math.sqrt(expected)
        upper = max(expected + band, float(booked))
        points.append(ForecastPoint(
            date=day,
            weekday=day.strftime("%A"),
            already_booked=booked,
            expected_bookings=round(expected, 2),
            lower=round(max(0.0, expected - band), 2),
            upper=round(upper, 2),
            workers_needed=math.ceil(upper / jobs_per_worker_per_day) if upper > 0 else 0,
            confidence=confidence,
            forecast_jobs=round(expected, 2),
            explanation=(
                f"{trade + ' ' if trade else ''}demand is based on the {method}; "
                f"{booked} booking{'s' if booked != 1 else ''} already on the calendar."
            ),
        ))

    return DemandForecast(
        trade=trade,
        horizon_days=horizon_days,
        history_days=history_days,
        history_bookings=history_bookings,
        method=method,
        total_expected=round(sum(p.expected_bookings for p in points), 2),
        points=points,
    )
