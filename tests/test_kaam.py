"""The worker's own portal: approval, summary, job replies, availability edits, history."""
from __future__ import annotations

from datetime import date

from app.services.voice import parse_availability

SITE = (23.18, 77.42)


def booking_payload(**extra) -> dict:
    return {"customer_name": "Test Household", "trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1],
            "scheduled_for": "2026-09-12T10:00", **extra}


def place_booking(client) -> int:
    response = client.post("/bookings", json=booking_payload())
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ── council approval ─────────────────────────────────────────────────────

def test_new_kaam_signup_is_pending_until_the_council_approves(make_client, council, customer):
    ravi = make_client("worker", name="Ravi", approved=False)
    worker_id = ravi.user["worker_id"]
    assert ravi.get(f"/workers/{worker_id}").json()["status"] == "pending"
    assert ravi.get("/workers/me/summary").json()["status"] == "pending"
    assert [w["id"] for w in council.get("/admin/workers/pending").json()] == [worker_id]

    # the engine does not offer a pending worker any work
    booking_id = place_booking(customer)
    assert council.post(f"/bookings/{booking_id}/assign").status_code == 409
    assert council.get(f"/bookings/{booking_id}/recommendations").json() == []

    # council can only activate once the worker has uploaded an Aadhaar
    ravi.post(f"/workers/{worker_id}/documents", json={"document_type": "aadhaar", "file_url": "uploads/aadhaar.jpg"})
    approved = council.post(f"/workers/{worker_id}/approve", json={"status": "active"})
    assert approved.status_code == 200 and approved.json()["status"] == "active"
    assert council.get("/admin/workers/pending").json() == []
    assert council.post(f"/bookings/{booking_id}/assign").json()["worker"]["id"] == worker_id


def test_only_the_council_approves(worker, customer):
    for c in (worker, customer):
        assert c.get("/admin/workers/pending").status_code == 403
        assert c.post(f"/workers/{worker.user['worker_id']}/approve", json={"status": "active"}).status_code == 403


def test_council_registered_workers_are_active_at_once(council):
    created = council.post("/workers", json={"name": "Meena", "trade": "electrical", "latitude": 23.2, "longitude": 77.4})
    assert created.json()["status"] == "active"


# ── summary ──────────────────────────────────────────────────────────────

def test_summary_shows_the_workers_own_share_and_rating(worker, customer, council):
    booking_id = place_booking(customer)
    council.post(f"/bookings/{booking_id}/assign")
    worker.post(f"/bookings/{booking_id}/complete", json={"amount": 1000})
    customer.post(f"/bookings/{booking_id}/rating", json={"rating": 5})

    s = worker.get("/workers/me/summary").json()
    assert s["completed_jobs"] == 1
    assert s["share_rupees"] == 850.0
    assert s["share_this_month_rupees"] == 850.0
    assert s["billed_this_month_rupees"] == 1000.0
    assert s["rating_count"] == 1 and s["rating"] == 5
    assert s["engagement_days"] == 1 and s["days_to_benefits"] == 89
    assert s["split_percent"] == {"worker": 85, "welfare_fund": 10, "platform_operations": 5}


def test_summary_counts_free_hours_and_jobs_awaiting_a_reply(worker, customer, council):
    worker_id = worker.user["worker_id"]
    worker.put(f"/workers/{worker_id}/availability", json={"windows": [
        {"date": None, "weekday": None, "start": "06:00", "end": "12:00", "available": True},   # 6 h every day
        {"date": None, "weekday": 6, "start": "00:00", "end": "23:59", "available": False},     # but not Sundays
    ]})
    assert worker.get("/workers/me/summary").json()["free_hours_this_week"] == 36.0
    booking_id = place_booking(customer)
    council.post(f"/bookings/{booking_id}/assign")
    assert worker.get("/workers/me/summary").json()["awaiting_reply"] == 1
    worker.post(f"/bookings/{booking_id}/accept")
    assert worker.get("/workers/me/summary").json()["awaiting_reply"] == 0


def test_customers_have_no_worker_summary(customer):
    assert customer.get("/workers/me/summary").status_code == 403


# ── accept / decline ─────────────────────────────────────────────────────

def test_accept_marks_the_assignment(worker, customer, council):
    booking_id = place_booking(customer)
    council.post(f"/bookings/{booking_id}/assign")
    reply = worker.post(f"/bookings/{booking_id}/accept")
    assert reply.status_code == 200 and reply.json()["status"] == "assigned"
    jobs = worker.get("/workers/me/jobs").json()
    assert jobs[0]["outcome"] == "accepted" and jobs[0]["accepted_at"]


def test_decline_hands_the_job_to_the_next_worker(make_client, customer, council):
    asha = make_client("worker", name="Asha")
    ravi = make_client("worker", name="Ravi")
    booking_id = place_booking(customer)
    first = council.post(f"/bookings/{booking_id}/assign").json()["worker"]["id"]
    chosen, other = (asha, ravi) if first == asha.user["worker_id"] else (ravi, asha)

    reply = chosen.post(f"/bookings/{booking_id}/decline", json={"reason": "too_far"})
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] == "assigned"
    assert reply.json()["reassigned_to"] == other.user["name"]

    detail = council.get(f"/bookings/{booking_id}").json()
    assert detail["assignment"]["worker"]["id"] == other.user["worker_id"]
    assert chosen.get(f"/bookings/{booking_id}").status_code == 403           # no longer theirs
    assert council.get(f"/workers/{chosen.user['worker_id']}").json()["jobs_this_week"] == 0
    history = chosen.get("/workers/me/jobs").json()
    assert history[0]["outcome"] == "declined" and history[0]["decline_reason"] == "too_far"


def test_decline_with_nobody_else_leaves_the_booking_pending(worker, customer, council):
    booking_id = place_booking(customer)
    council.post(f"/bookings/{booking_id}/assign")
    reply = worker.post(f"/bookings/{booking_id}/decline", json={"reason": "unwell", "mark_busy_today": True})
    assert reply.json() == {"booking_id": booking_id, "status": "pending", "reassigned_to": None}
    assert council.get(f"/bookings/{booking_id}").json()["booking"]["status"] == "pending"
    # the same worker is not offered it again
    assert council.post(f"/bookings/{booking_id}/assign").status_code == 409
    busy = worker.get(f"/workers/{worker.user['worker_id']}").json()["availability"]
    assert busy and busy[-1]["available"] is False and busy[-1]["end"] == "23:59"


def test_only_the_assigned_worker_can_reply(make_client, customer, council):
    asha, ravi = make_client("worker", name="Asha"), make_client("worker", name="Ravi")
    booking_id = place_booking(customer)
    first = council.post(f"/bookings/{booking_id}/assign").json()["worker"]["id"]
    other = ravi if first == asha.user["worker_id"] else asha
    assert other.post(f"/bookings/{booking_id}/accept").status_code == 403
    assert other.post(f"/bookings/{booking_id}/decline", json={"reason": "other"}).status_code == 403
    assert customer.post(f"/bookings/{booking_id}/accept").status_code == 403


def test_replies_need_an_assigned_booking(worker, customer, council):
    booking_id = place_booking(customer)
    assert worker.post(f"/bookings/{booking_id}/accept").status_code in (403, 409)
    assert worker.post("/bookings/999/decline", json={"reason": "other"}).status_code == 404


# ── availability edits ───────────────────────────────────────────────────

def test_worker_can_edit_their_windows(worker):
    worker_id = worker.user["worker_id"]
    windows = [
        {"date": None, "weekday": 0, "start": "06:00", "end": "12:00", "available": True},
        {"date": None, "weekday": 1, "start": "06:00", "end": "12:00", "available": True},
    ]
    assert worker.put(f"/workers/{worker_id}/availability", json={"windows": windows}).json()["availability"] == windows

    patched = worker.patch(f"/workers/{worker_id}/availability/1", json={"available": False, "end": "20:00"}).json()
    assert patched["availability"][1] == {"date": None, "weekday": 1, "start": "06:00", "end": "20:00", "available": False}
    assert worker.patch(f"/workers/{worker_id}/availability/1", json={"end": "05:00"}).status_code == 422

    removed = worker.delete(f"/workers/{worker_id}/availability/0").json()
    assert len(removed["availability"]) == 1 and removed["availability"][0]["weekday"] == 1
    assert worker.delete(f"/workers/{worker_id}/availability/5").status_code == 404


def test_worker_cannot_edit_another_workers_windows(make_client):
    asha, ravi = make_client("worker", name="Asha"), make_client("worker", name="Ravi")
    other = ravi.user["worker_id"]
    assert asha.put(f"/workers/{other}/availability", json={"windows": []}).status_code == 403
    assert asha.delete(f"/workers/{other}/availability/0").status_code == 403


# ── history ──────────────────────────────────────────────────────────────

def test_jobs_history_carries_money_and_rating(worker, customer, council):
    booking_id = place_booking(customer)
    council.post(f"/bookings/{booking_id}/assign")
    worker.post(f"/bookings/{booking_id}/complete", json={"amount": 600})
    customer.post(f"/bookings/{booking_id}/rating", json={"rating": 4, "comment": "Quick"})

    (job,) = worker.get("/workers/me/jobs").json()
    assert job["outcome"] == "completed"
    assert job["billed_rupees"] == 600.0 and job["share_rupees"] == 510.0
    assert job["rating"] == 4 and job["rating_comment"] == "Quick"
    assert job["customer_name"] == "Test Household"


# ── parser honesty ───────────────────────────────────────────────────────

def test_parser_understands_misspelt_tomorrow_and_flags_a_missing_day():
    today = date(2026, 9, 11)
    result = parse_availability("i am available at 10 tommorrow", reference_date=today)
    assert result.windows[0].date == date(2026, 9, 12)
    assert result.windows[0].start == "10:00"
    assert any("start time" in a for a in result.assumptions)
    assert not any("No day" in a for a in result.assumptions)

    guessed = parse_availability("free at 10", reference_date=today)
    assert guessed.windows[0].date is None and guessed.windows[0].weekday is None
    assert any("No day" in a for a in guessed.assumptions)
    assert guessed.confidence <= 0.5

    exact = parse_availability("kal subah 9 se 12 tak free hoon", reference_date=today)
    assert exact.assumptions == []


def test_parser_expands_weekday_ranges():
    today = date(2026, 9, 11)
    result = parse_availability("somvar se shukravar subah khali hoon", reference_date=today)
    assert [w.weekday for w in result.windows] == [0, 1, 2, 3, 4]
    assert all(w.start == "06:00" and w.end == "12:00" and w.available for w in result.windows)
    english = parse_availability("free monday to wednesday", reference_date=today)
    assert [w.weekday for w in english.windows] == [0, 1, 2]
    wrap = parse_availability("friday to monday busy", reference_date=today)
    assert [w.weekday for w in wrap.windows] == [4, 5, 6, 0]
    assert not any(w.available for w in wrap.windows)
