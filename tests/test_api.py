"""Workers, bookings, voice, allocation preview and forecast endpoints."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

SITE = (23.1800, 77.4200)


@pytest.fixture
def client(council):
    """This suite calls council-only endpoints (workers, forecast, recommendations); run it signed in as council."""
    return council


def worker_payload(name="Asha", trade="plumbing", lat=SITE[0], lon=SITE[1], **extra) -> dict:
    return {"name": name, "trade": trade, "latitude": lat, "longitude": lon, **extra}


def booking_payload(trade="plumbing", lat=SITE[0], lon=SITE[1], **extra) -> dict:
    return {"customer_name": "Test Household", "trade": trade, "latitude": lat, "longitude": lon,
            "scheduled_for": "2026-09-12T10:00", **extra}


# ── workers ──────────────────────────────────────────────────────────────

def test_create_and_fetch_worker(client):
    created = client.post("/workers", json=worker_payload(trade="  Plumbing ", phone="9876543210"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] == 1
    assert body["trade"] == "plumbing"          # normalised
    assert body["jobs_this_week"] == 0 and body["rating"] is None and body["availability"] == []

    assert client.get("/workers/1").json()["name"] == "Asha"
    assert client.get("/workers/99").status_code == 404
    assert [w["id"] for w in client.get("/workers").json()] == [1]


def test_list_workers_filters_by_trade(client):
    client.post("/workers", json=worker_payload("Asha", "plumbing"))
    client.post("/workers", json=worker_payload("Meena", "electrical"))
    assert [w["name"] for w in client.get("/workers", params={"trade": "Electrical"}).json()] == ["Meena"]


def test_worker_validation(client):
    assert client.post("/workers", json={"name": "", "trade": "plumbing", "latitude": 0, "longitude": 0}).status_code == 422
    assert client.post("/workers", json=worker_payload(lat=95)).status_code == 422
    assert client.post("/workers", json=worker_payload(rating=7)).status_code == 422


# ── voice availability ───────────────────────────────────────────────────

def test_voice_availability_is_parsed_and_stored_on_worker(client):
    worker_id = client.post("/workers", json=worker_payload()).json()["id"]

    response = client.post(f"/workers/{worker_id}/availability/voice",
                           json={"transcript": "kal subah free hoon", "reference_date": "2026-09-11"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parsed"]["windows"] == [{"date": "2026-09-12", "weekday": None, "start": "06:00", "end": "12:00", "available": True}]
    assert body["parsed"]["language"] == "mixed"
    assert body["worker"]["availability"] == body["parsed"]["windows"]
    assert client.get(f"/workers/{worker_id}").json()["availability"] == body["parsed"]["windows"]


def test_voice_availability_can_append_instead_of_replace(client):
    worker_id = client.post("/workers", json=worker_payload()).json()["id"]
    client.post(f"/workers/{worker_id}/availability/voice", json={"transcript": "somvar ko subah"})
    client.post(f"/workers/{worker_id}/availability/voice", json={"transcript": "mangalvar ko shaam", "replace": False})
    stored = client.get(f"/workers/{worker_id}").json()["availability"]
    assert [(w["weekday"], w["start"]) for w in stored] == [(0, "06:00"), (1, "16:00")]


def test_voice_endpoint_rejects_unintelligible_transcript_and_unknown_worker(client):
    worker_id = client.post("/workers", json=worker_payload()).json()["id"]
    response = client.post(f"/workers/{worker_id}/availability/voice", json={"transcript": "theek hai"})
    assert response.status_code == 422
    assert response.json()["detail"]["parsed"]["windows"] == []
    assert client.post("/workers/999/availability/voice", json={"transcript": "kal subah"}).status_code == 404


def test_voice_parse_dry_run_does_not_need_a_worker(client):
    body = client.post("/voice/parse", json={"transcript": "busy on sunday"}).json()
    assert body["windows"] == [{"date": None, "weekday": 6, "start": "00:00", "end": "23:59", "available": False}]


# ── bookings ─────────────────────────────────────────────────────────────

def test_create_and_list_bookings(client):
    created = client.post("/bookings", json=booking_payload(address="12 MP Nagar"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] == 1 and body["status"] == "pending"
    assert body["scheduled_for"] == "2026-09-12T10:00:00"
    assert body["address"] == "12 MP Nagar"

    client.post("/bookings", json=booking_payload(trade="electrical"))
    assert len(client.get("/bookings").json()) == 2
    assert [b["trade"] for b in client.get("/bookings", params={"trade": "electrical"}).json()] == ["electrical"]
    assert len(client.get("/bookings", params={"status": "pending"}).json()) == 2
    assert client.get("/bookings", params={"status": "completed"}).json() == []


def test_booking_without_slot_means_as_soon_as_possible(client):
    payload = booking_payload()
    del payload["scheduled_for"]
    assert client.post("/bookings", json=payload).json()["scheduled_for"] is None


def test_booking_validation(client):
    assert client.post("/bookings", json={"customer_name": "X"}).status_code == 422
    assert client.post("/bookings", json=booking_payload(scheduled_for="not a date")).status_code == 422


# ── allocation preview ───────────────────────────────────────────────────

def test_recommendations_preview_ranks_without_assigning(client):
    client.post("/workers", json=worker_payload("Asha", "plumbing", rating=4.8))
    client.post("/workers", json=worker_payload("Ravi", "plumbing", lat=SITE[0] + 0.02, rating=4.5))
    client.post("/workers", json=worker_payload("Meena", "electrical"))
    booking_id = client.post("/bookings", json=booking_payload()).json()["id"]

    response = client.get(f"/bookings/{booking_id}/recommendations")

    assert response.status_code == 200, response.text
    ranked = response.json()
    assert [r["worker_name"] for r in ranked] == ["Asha", "Ravi"]
    assert ranked[0]["rank"] == 1 and ranked[0]["score"] > ranked[1]["score"]
    assert set(ranked[0]["score_breakdown"]) == {"proximity", "fairness", "rating", "availability"}
    assert client.get(f"/bookings/{booking_id}").json()["booking"]["status"] == "pending"   # nothing assigned
    assert client.get("/bookings/999/recommendations").status_code == 404
    assert client.get(f"/bookings/{booking_id}/recommendations", params={"top_k": 1}).json()[0]["worker_name"] == "Asha"


def test_ad_hoc_recommendation_request(client):
    client.post("/workers", json=worker_payload("Asha", "plumbing"))
    response = client.post("/allocation/recommend", json={"trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1]})
    assert response.status_code == 200
    assert [r["worker_id"] for r in response.json()] == [1]
    assert client.post("/allocation/recommend", json={"trade": "carpentry", "latitude": SITE[0], "longitude": SITE[1]}).json() == []


# ── forecast ─────────────────────────────────────────────────────────────

def test_forecast_uses_booking_history_and_counts_future_slots(client):
    today = date(2026, 9, 11)
    for back in range(1, 15):                      # two weeks of one plumbing booking a day
        day = today - timedelta(days=back)
        client.post("/bookings", json=booking_payload(scheduled_for=f"{day.isoformat()}T10:00"))
    client.post("/bookings", json=booking_payload(scheduled_for="2026-09-13T11:00"))   # already on the calendar
    client.post("/bookings", json=booking_payload(trade="electrical", scheduled_for="2026-09-10T11:00"))

    response = client.get("/forecast", params={"trade": "plumbing", "days": 7, "today": today.isoformat()})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["trade"] == "plumbing" and body["history_bookings"] == 14
    assert len(body["points"]) == 7
    sunday = next(p for p in body["points"] if p["date"] == "2026-09-13")
    assert sunday["already_booked"] == 1 and sunday["expected_bookings"] >= 1
    assert all(p["workers_needed"] >= 1 for p in body["points"])

    everything = client.get("/forecast", params={"today": today.isoformat()}).json()
    assert everything["trade"] is None and everything["history_bookings"] == 15
    assert client.get("/forecast", params={"days": 0}).status_code == 422


def test_root_health(client):
    assert client.get("/").json()["status"] == "ok"


# ── web app ──────────────────────────────────────────────────────────────

def test_web_app_is_served_with_spa_fallback_or_explains_how_to_build(client):
    from pathlib import Path

    response = client.get("/app/")
    if (Path(__file__).resolve().parent.parent / "frontend" / "dist").is_dir():
        assert response.status_code == 200 and response.headers["content-type"].startswith("text/html")
        assert client.get("/app/worker").text == response.text                 # SPA route -> index.html
        assert client.get("/app/manifest.webmanifest").status_code == 200
        assert client.get("/app/..%2F..%2Fapp%2Fmain.py").status_code == 404     # never escapes dist/
        assert client.get("/app/img/missing.jpg").status_code == 404               # missing files 404, not the SPA shell
    else:
        assert response.status_code == 404 and "npm run build" in response.json()["detail"]
