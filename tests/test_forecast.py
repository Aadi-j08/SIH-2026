"""Demand forecast."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.services.forecast import forecast_demand, weekday_factors

TODAY = date(2026, 9, 11)   # Friday


def history(days_back: int, per_weekday: dict[int, int]) -> list[date]:
    """One entry per booking: `per_weekday[weekday]` bookings on each of the last `days_back` days."""
    out = []
    for back in range(1, days_back + 1):
        day = TODAY - timedelta(days=back)
        out.extend([day] * per_weekday.get(day.weekday(), 0))
    return out


def test_no_history_gives_zero_forecast_with_honest_method():
    result = forecast_demand([], horizon_days=7, today=TODAY)
    assert result.method == "no booking history yet"
    assert result.history_bookings == 0
    assert result.total_expected == 0
    assert len(result.points) == 7
    assert all(p.expected_bookings == p.lower == p.upper == 0 and p.workers_needed == 0 for p in result.points)


def test_horizon_starts_today_and_has_requested_length():
    result = forecast_demand(history(28, {0: 2}), horizon_days=10, today=TODAY)
    assert [p.date for p in result.points] == [TODAY + timedelta(days=i) for i in range(10)]
    assert result.points[0].weekday == "Friday"
    assert result.horizon_days == 10 and result.history_days == 28


def test_weekday_seasonality_is_learned_from_history():
    # Mondays are busy (4 bookings), Sundays are dead (0), other days 1.
    demand = history(28, {0: 4, 1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 0})
    result = forecast_demand(demand, horizon_days=7, today=TODAY)
    by_weekday = {p.weekday: p for p in result.points}
    assert by_weekday["Monday"].expected_bookings > by_weekday["Wednesday"].expected_bookings > by_weekday["Sunday"].expected_bookings
    assert by_weekday["Sunday"].expected_bookings > 0     # shrinkage: a quiet weekday is not zeroed out
    assert by_weekday["Monday"].workers_needed >= by_weekday["Sunday"].workers_needed
    assert result.history_bookings == len(demand)


def test_weekday_factors_average_to_one_and_are_flat_with_uniform_history():
    first = TODAY - timedelta(days=28)
    factors = weekday_factors([2] * 28, first)
    assert sum(factors.values()) / 7 == pytest.approx(1.0)
    assert all(f == pytest.approx(1.0) for f in factors.values())


def test_already_booked_slots_raise_the_floor_of_the_forecast():
    tuesday = TODAY + timedelta(days=4)
    demand = history(28, {d: 1 for d in range(7)}) + [datetime(tuesday.year, tuesday.month, tuesday.day, 10)] * 5
    result = forecast_demand(demand, horizon_days=7, today=TODAY)
    point = next(p for p in result.points if p.date == tuesday)
    assert point.already_booked == 5
    assert point.expected_bookings == 5 and point.upper == pytest.approx(5 + 1.28 * 5 ** 0.5, abs=0.01)
    assert point.workers_needed == 3       # ceil(7.86 upper / 3 jobs per worker per day): plan for the busy case


def test_accepts_sqlite_style_timestamp_strings():
    demand = [(TODAY - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"), (TODAY - timedelta(days=1)).isoformat() + "T09:30:00"]
    result = forecast_demand(demand, horizon_days=3, today=TODAY)
    assert result.history_bookings == 2
    assert all(p.lower <= p.expected_bookings <= p.upper for p in result.points)
