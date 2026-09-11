"""Tests for the booking flow endpoints.

Run with:  .venv/bin/python -m pytest -q
"""
from __future__ import annotations

import threading
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

# ── Adapt to your project ────────────────────────────────────────────────
# These are the only lines that assume names from the existing codebase.
from app import database              # your SQLite setup module
from app.main import app              # your FastAPI instance

DB_PATH_ATTRIBUTE = "DB_PATH"         # variable in app/database.py holding the file path
DB_PATH_ENV_VAR = "SAHAKARSETU_DB"    # env var your settings read, if any
INIT_DB_FUNCTION = "init_db"          # function in app/database.py that creates the tables


def worker_payload(name: str, trade: str, lat: float, lon: float) -> dict:
    """Body for the existing POST /workers."""
    return {"name": name, "trade": trade, "latitude": lat, "longitude": lon}


def booking_payload(trade: str, lat: float, lon: float) -> dict:
    """Body for the existing POST /bookings."""
    return {"customer_name": "Test Household", "trade": trade, "latitude": lat,
            "longitude": lon, "scheduled_for": "2026-09-12T10:00"}
# ─────────────────────────────────────────────────────────────────────────

from app.booking_flow_db import booking_flow_connection, open_connection  # noqa: E402
from app.services import booking_flow  # noqa: E402
from app.services.allocation_bridge import rank_workers  # noqa: E402
from app.services.ledger import split_payment  # noqa: E402

SITE = (23.1800, 77.4200)  # booking location used throughout


@pytest.fixture
def client(tmp_path, monkeypatch, make_client):
    # Endpoints need a signed-in user; the council role may do everything this suite exercises.
    yield make_client("council")


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = open_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params)]
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> None:
    conn = open_connection()
    try:
        conn.execute(sql, params)
    finally:
        conn.close()


def add_worker(client, name, trade, lat, lon, jobs_this_week=0, rating=None) -> int:
    response = client.post("/workers", json=worker_payload(name, trade, lat, lon))
    assert response.status_code in (200, 201), response.text
    worker_id = response.json()["id"]
    execute("UPDATE workers SET jobs_this_week = ? WHERE id = ?", (jobs_this_week, worker_id))
    if rating is not None:
        execute("UPDATE workers SET rating = ? WHERE id = ?", (rating, worker_id))
    return worker_id


def add_booking(client, trade="plumbing", lat=SITE[0], lon=SITE[1]) -> int:
    response = client.post("/bookings", json=booking_payload(trade, lat, lon))
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


@pytest.fixture
def crew(client):
    """Asha dominates every factor, so any fair engine should pick her for plumbing."""
    return {
        "asha": add_worker(client, "Asha", "plumbing", SITE[0], SITE[1], jobs_this_week=0, rating=4.8),
        "ravi": add_worker(client, "Ravi", "plumbing", SITE[0] + 0.009, SITE[1], jobs_this_week=5, rating=4.5),
        "imran": add_worker(client, "Imran", "plumbing", SITE[0] + 0.05, SITE[1], jobs_this_week=2, rating=4.2),
        "meena": add_worker(client, "Meena", "electrical", SITE[0], SITE[1], jobs_this_week=3, rating=4.0),
    }


def jobs_of(worker_id: int) -> int:
    return query("SELECT jobs_this_week FROM workers WHERE id = ?", (worker_id,))[0]["jobs_this_week"]


def assign(client, booking_id: int):
    return client.post(f"/bookings/{booking_id}/assign")


def complete(client, booking_id: int, amount=500):
    return client.post(f"/bookings/{booking_id}/complete", json={"amount": amount})


# ── POST /bookings/{id}/assign ───────────────────────────────────────────

def test_assign_picks_engine_top_worker_and_updates_everything(client, crew):
    booking_id = add_booking(client)
    booking = query("SELECT * FROM bookings WHERE id = ?", (booking_id,))[0]
    expected = rank_workers(booking, query("SELECT * FROM workers"))[0]

    response = assign(client, booking_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["worker"]["id"] == expected.worker_id == crew["asha"]
    assert body["status"] == "assigned"
    assert body["score"] == pytest.approx(expected.score)
    assert body["score_breakdown"]
    assert body["explanation"]

    rows = query("SELECT * FROM assignments WHERE booking_id = ?", (booking_id,))
    assert len(rows) == 1 and rows[0]["worker_id"] == crew["asha"]
    assert query("SELECT status FROM bookings WHERE id = ?", (booking_id,))[0]["status"] == "assigned"
    assert jobs_of(crew["asha"]) == 1
    assert body["worker"]["jobs_this_week"] == 1
    assert jobs_of(crew["ravi"]) == 5  # nobody else touched


def test_assign_unknown_booking_returns_404(client, crew):
    assert assign(client, 9999).status_code == 404


def test_assign_twice_is_rejected_without_side_effects(client, crew):
    booking_id = add_booking(client)
    assert assign(client, booking_id).status_code == 200

    second = assign(client, booking_id)

    assert second.status_code == 409
    assert len(query("SELECT * FROM assignments WHERE booking_id = ?", (booking_id,))) == 1
    assert jobs_of(crew["asha"]) == 1


def test_assign_with_no_workers_returns_409_and_writes_nothing(client):
    booking_id = add_booking(client)

    response = assign(client, booking_id)

    assert response.status_code == 409
    assert query("SELECT * FROM assignments") == []
    assert query("SELECT status FROM bookings WHERE id = ?", (booking_id,))[0]["status"] == "pending"


def test_assign_rolls_back_everything_if_last_step_fails(client, crew, monkeypatch):
    booking_id = add_booking(client)

    def fail(*_args):
        raise RuntimeError("simulated crash while updating jobs_this_week")

    monkeypatch.setattr(booking_flow, "_increment_worker_jobs", fail)
    with TestClient(app, raise_server_exceptions=False, cookies=client.cookies) as failing_client:
        response = assign(failing_client, booking_id)

    assert response.status_code == 500
    assert query("SELECT * FROM assignments WHERE booking_id = ?", (booking_id,)) == []
    assert query("SELECT status FROM bookings WHERE id = ?", (booking_id,))[0]["status"] == "pending"
    assert jobs_of(crew["asha"]) == 0


def test_concurrent_assign_requests_assign_exactly_once(client, crew):
    booking_id = add_booking(client)
    barrier = threading.Barrier(5)
    outcomes: list[str] = []

    def attempt():
        barrier.wait()
        try:
            with booking_flow_connection() as conn:
                booking_flow.assign_booking(conn, booking_id)
            outcomes.append("assigned")
        except booking_flow.InvalidBookingState:
            outcomes.append("conflict")

    threads = [threading.Thread(target=attempt) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["assigned"] + ["conflict"] * 4
    assert len(query("SELECT * FROM assignments WHERE booking_id = ?", (booking_id,))) == 1
    assert jobs_of(crew["asha"]) == 1


# ── GET /bookings/{id} ───────────────────────────────────────────────────

def test_get_booking_before_assignment(client, crew):
    booking_id = add_booking(client)

    body = client.get(f"/bookings/{booking_id}").json()

    assert body["booking"]["id"] == booking_id
    assert body["booking"]["status"] == "pending"
    assert body["assignment"] is None
    assert body["payment_ledger"] == []
    assert body["rating"] is None


def test_get_booking_shows_full_lifecycle(client, crew):
    booking_id = add_booking(client)
    assign(client, booking_id)
    complete(client, booking_id)
    client.post(f"/bookings/{booking_id}/rating", json={"rating": 5, "comment": "On time"})

    body = client.get(f"/bookings/{booking_id}").json()

    assert body["booking"]["status"] == "completed"
    assert body["assignment"]["worker"]["id"] == crew["asha"]
    assert body["assignment"]["score_breakdown"]
    assert body["assignment"]["explanation"]
    assert [e["party"] for e in body["payment_ledger"]] == ["worker", "welfare_fund", "platform_operations"]
    assert body["rating"]["rating"] == 5


def test_get_unknown_booking_returns_404(client):
    assert client.get("/bookings/9999").status_code == 404


# ── POST /bookings/{id}/complete ─────────────────────────────────────────

def test_complete_writes_85_10_5_ledger(client, crew):
    booking_id = add_booking(client)
    assign(client, booking_id)

    response = complete(client, booking_id, 500)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    shares = {e["party"]: e["amount_rupees"] for e in body["ledger"]}
    assert shares == {"worker": 425.0, "welfare_fund": 50.0, "platform_operations": 25.0}
    worker_entry = next(e for e in body["ledger"] if e["party"] == "worker")
    assert worker_entry["worker_id"] == crew["asha"]
    assert query("SELECT status FROM bookings WHERE id = ?", (booking_id,))[0]["status"] == "completed"


def test_complete_never_loses_a_paisa_to_rounding(client, crew):
    booking_id = add_booking(client)
    assign(client, booking_id)

    body = complete(client, booking_id, 333.33).json()

    assert sum(e["amount_paise"] for e in body["ledger"]) == 33333


def test_complete_requires_an_assigned_booking(client, crew):
    booking_id = add_booking(client)
    assert complete(client, booking_id).status_code == 409  # still pending
    assign(client, booking_id)
    assert complete(client, booking_id).status_code == 200
    assert complete(client, booking_id).status_code == 409  # already completed
    assert len(query("SELECT * FROM payment_ledger WHERE booking_id = ?", (booking_id,))) == 3


@pytest.mark.parametrize("amount", [0, -10, "abc", 12.345])
def test_complete_rejects_invalid_amounts(client, crew, amount):
    booking_id = add_booking(client)
    assign(client, booking_id)
    assert complete(client, booking_id, amount).status_code == 422


def test_complete_unknown_booking_returns_404(client):
    assert complete(client, 9999).status_code == 404


# ── POST /bookings/{id}/rating ───────────────────────────────────────────

def test_rating_updates_worker_average(client, crew):
    booking_id = add_booking(client)
    assign(client, booking_id)
    complete(client, booking_id)

    response = client.post(f"/bookings/{booking_id}/rating", json={"rating": 5})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["worker_id"] == crew["asha"]
    assert body["worker_rating_count"] == 1
    assert body["worker_average_rating"] == pytest.approx(4.9)  # (starting 4.8 + 5) / 2


def test_rating_before_completion_is_rejected(client, crew):
    booking_id = add_booking(client)
    assign(client, booking_id)
    assert client.post(f"/bookings/{booking_id}/rating", json={"rating": 4}).status_code == 409


def test_booking_can_only_be_rated_once(client, crew):
    booking_id = add_booking(client)
    assign(client, booking_id)
    complete(client, booking_id)
    assert client.post(f"/bookings/{booking_id}/rating", json={"rating": 4}).status_code == 200
    assert client.post(f"/bookings/{booking_id}/rating", json={"rating": 1}).status_code == 409


@pytest.mark.parametrize("rating", [0, 6, "five"])
def test_rating_must_be_1_to_5(client, crew, rating):
    booking_id = add_booking(client)
    assign(client, booking_id)
    complete(client, booking_id)
    assert client.post(f"/bookings/{booking_id}/rating", json={"rating": rating}).status_code == 422


def test_rating_unknown_booking_returns_404(client):
    assert client.post("/bookings/9999/rating", json={"rating": 5}).status_code == 404


# ── GET /admin/dashboard ─────────────────────────────────────────────────

def test_dashboard_on_empty_database(client):
    response = client.get("/admin/dashboard")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["bookings"] == {"total": 0, "pending": 0, "assigned": 0, "completed": 0}
    assert body["money"]["gross_rupees"] == 0
    assert body["fairness"]["jobs_gini"] == 0.0


def test_dashboard_reflects_bookings_money_and_engagement(client, crew):
    done = add_booking(client)
    assign(client, done)
    complete(client, done, 500)
    client.post(f"/bookings/{done}/rating", json={"rating": 5})
    in_progress = add_booking(client)
    assign(client, in_progress)
    add_booking(client)

    body = client.get("/admin/dashboard").json()

    assert body["bookings"] == {"total": 3, "pending": 1, "assigned": 1, "completed": 1}
    assert body["money"] == {
        "gross_rupees": 500.0,
        "worker_payouts_rupees": 425.0,
        "welfare_fund_rupees": 50.0,
        "platform_operations_rupees": 25.0,
    }
    assert body["ratings"] == {"count": 1, "average": 5.0}
    paid = next(w for w in body["workers"] if w["completed_jobs"] == 1)
    assert paid["earnings_rupees"] == 425.0
    assert paid["engagement_days"] == 1
    assert paid["days_to_social_security_eligibility"] == 89
    assert 0 <= body["fairness"]["jobs_gini"] <= 1
    assert len(body["recent_assignments"]) == 2


# ── pure functions ───────────────────────────────────────────────────────

def test_split_payment_shares_add_up():
    for paise in (1, 99, 100, 33333, 1_000_000):
        shares = split_payment(paise)
        assert sum(shares.values()) == paise
    assert split_payment(100_00) == {"worker": 85_00, "welfare_fund": 10_00, "platform_operations": 5_00}


def test_gini_measures_how_evenly_jobs_are_shared():
    assert booking_flow.gini([3, 3, 3, 3]) == 0.0
    assert booking_flow.gini([0, 0, 0, 10]) == 0.75
    assert booking_flow.gini([]) == 0.0


def test_decimal_amounts_convert_exactly():
    from app.services.ledger import rupees_to_paise
    assert rupees_to_paise(Decimal("349.50")) == 34950
