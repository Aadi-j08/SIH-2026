"""Staffing forecast: expected bookings and workers needed vs. workers actually available."""
from __future__ import annotations

from datetime import date, timedelta

from app.schemas import AvailabilityWindow, DemandForecast, ForecastPoint, WorkerProfile
from app.services.staffing import available_workers_on, staffing_forecast

SITE = (23.18, 77.42)
MONDAY = date(2026, 9, 14)


def worker(id, trade="plumbing", windows=()):
    return WorkerProfile(id=id, name=f"W{id}", trade=trade, latitude=SITE[0], longitude=SITE[1], availability=list(windows))


def forecast(points: list[tuple[date, float, int]]) -> DemandForecast:
    return DemandForecast(
        trade="plumbing", horizon_days=len(points), history_days=28, history_bookings=40, method="test", total_expected=0,
        points=[ForecastPoint(date=d, weekday=d.strftime("%A"), already_booked=0, expected_bookings=e, lower=0, upper=e, workers_needed=n)
                for d, e, n in points],
    )


def test_shortage_is_workers_needed_minus_available_never_negative():
    busy_monday = AvailabilityWindow(date=MONDAY, start="00:00", end="23:59", available=False)
    workers = [worker(1), worker(2, windows=[busy_monday]), worker(3, trade="electrical")]
    demand = forecast([(MONDAY, 4.0, 2), (MONDAY + timedelta(days=1), 1.0, 1)])

    result = staffing_forecast(demand, workers, trade="plumbing")

    assert result.trade == "plumbing"
    assert [(d.available_workers, d.shortage) for d in result.days] == [(1, 1), (2, 0)]
    assert (result.peak_day, result.expected_bookings, result.workers_needed, result.available_workers, result.shortage) == (MONDAY, 4.0, 2, 1, 1)
    assert result.recommendation == "Request availability from 1 additional plumbing worker for Monday 2026-09-14"
    assert result.confidence == result.days[0].confidence
    assert "active workers" in result.explanation


def test_enough_workers_gives_no_shortage_and_says_so():
    demand = forecast([(MONDAY, 2.0, 1)])
    result = staffing_forecast(demand, [worker(1), worker(2)], trade="plumber")
    assert result.shortage == 0 and result.available_workers == 2
    assert result.recommendation == "Enough plumbing workers are available for the next 1 days."


def test_availability_counts_declared_free_and_unknown_but_not_busy():
    free_mondays = AvailabilityWindow(weekday=0, start="06:00", end="20:00")
    busy_mondays = AvailabilityWindow(weekday=0, start="06:00", end="20:00", available=False)
    assert available_workers_on([worker(1, windows=[free_mondays]), worker(2), worker(3, windows=[busy_mondays])], MONDAY, "plumbing") == 2


def test_plural_recommendation():
    demand = forecast([(MONDAY, 9.0, 3)])
    result = staffing_forecast(demand, [], trade="cleaning")
    assert result.shortage == 3
    assert result.recommendation.startswith("Request availability from 3 additional cleaning workers")


# ── endpoint ─────────────────────────────────────────────────────────────

def test_staffing_endpoint_compares_forecast_with_available_workers(council, make_client):
    today = date(2026, 9, 11)
    asha = make_client("worker", name="Asha", trade="plumbing")
    make_client("worker", name="Ravi", trade="plumbing")
    make_client("worker", name="Meena", trade="electrical")
    # Asha is busy tomorrow; a steady history of 3 plumbing bookings a day drives the forecast
    asha.post(f"/workers/{asha.user['worker_id']}/availability/voice", json={"transcript": "kal nahi aa sakta", "reference_date": today.isoformat()})
    for back in range(1, 15):
        for _ in range(3):
            council.post("/bookings", json={"customer_name": "H", "trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1],
                                            "scheduled_for": f"{(today - timedelta(days=back)).isoformat()}T10:00"})

    response = council.get("/forecast/staffing", params={"trade": "plumber", "days": 3, "today": today.isoformat()})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trade"] == "plumbing" and body["area"] is None and body["horizon_days"] == 3
    by_date = {d["date"]: d for d in body["days"]}
    tomorrow = by_date[(today + timedelta(days=1)).isoformat()]
    assert tomorrow["available_workers"] == 1                       # Asha declared busy, Ravi counts, Meena is electrical
    assert by_date[today.isoformat()]["available_workers"] == 2
    for d in body["days"]:
        assert d["workers_needed"] >= 1
        assert d["shortage"] == max(0, d["workers_needed"] - d["available_workers"])
    assert body["shortage"] == max(d["shortage"] for d in body["days"])
    assert body["expected_bookings"] > 0 and body["workers_needed"] >= 1
    assert body["recommendation"]


def test_staffing_endpoint_can_narrow_to_an_area(council, make_client):
    make_client("worker", name="Asha", trade="plumbing", locality="Kolar Road")
    make_client("worker", name="Ravi", trade="plumbing", locality="MP Nagar")
    council.post("/bookings", json={"customer_name": "H", "trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1],
                                    "address": "12 Kolar Road", "scheduled_for": "2026-09-13T10:00"})

    body = council.get("/forecast/staffing", params={"trade": "plumbing", "days": 3, "today": "2026-09-11", "area": "kolar road"}).json()
    assert body["area"] == "kolar road"
    assert all(d["available_workers"] == 1 for d in body["days"])   # only Asha works in Kolar Road
    assert next(d for d in body["days"] if d["date"] == "2026-09-13")["expected_bookings"] >= 1   # the scheduled booking counts


def test_staffing_endpoint_is_council_only(customer, worker, client):
    assert client.get("/forecast/staffing", params={"trade": "plumbing"}).status_code == 401
    assert customer.get("/forecast/staffing", params={"trade": "plumbing"}).status_code == 403
    assert worker.get("/forecast/staffing", params={"trade": "plumbing"}).status_code == 403
    assert client.get("/forecast/staffing").status_code == 401
