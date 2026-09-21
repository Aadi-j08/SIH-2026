"""Community rate card, agreed-price settlement, and the live event stream."""
from __future__ import annotations

from app import events

SITE = (23.18, 77.42)


def place_and_assign(customer, council, worker=None, trade: str = "plumbing") -> int:
    r = customer.post("/bookings", json={"customer_name": "Test Household", "trade": trade, "latitude": SITE[0], "longitude": SITE[1],
                                         "scheduled_for": "2026-09-12T10:00"})
    assert r.status_code == 201, r.text
    booking_id = r.json()["id"]
    assert council.post(f"/bookings/{booking_id}/assign").status_code == 200
    if worker:
        worker.post(f"/bookings/{booking_id}/verify-arrival", json={"photo_data_uri": "data:image/jpeg;base64,...", "latitude": 1.0, "longitude": 1.0, "timestamp": "2026-09-12T11:00Z"})
        worker.post(f"/bookings/{booking_id}/start-work", json={"timestamp": "2026-09-12T11:10Z"})
        worker.post(f"/bookings/{booking_id}/verify-completion", json={"photo_data_uri": "data:image/jpeg;base64,...", "latitude": 1.0, "longitude": 1.0, "timestamp": "2026-09-12T12:00Z"})
    return booking_id


# ── rate card ────────────────────────────────────────────────────────────

def test_rate_card_has_every_trade_and_quotes_from_it(customer):
    card = customer.get("/rates").json()
    assert [r["trade"] for r in card][:5] == ["plumbing", "electrical", "carpentry", "painting", "cleaning"]
    q = customer.get("/rates/quote?trade=plumber&hours=1.5&materials=80").json()
    assert q["trade"] == "plumbing"
    assert q["standard_rupees"] == 150 + 1.5 * 250 + 80
    assert q["min_fair_rupees"] < q["standard_rupees"] < q["max_fair_rupees"]
    # below the minimum billable time still bills the minimum
    assert customer.get("/rates/quote?trade=cleaning&hours=0.5").json()["billable_hours"] == 2


def test_only_the_council_edits_the_card(council, worker, customer):
    for c in (worker, customer):
        assert c.put("/rates/plumbing", json={"hourly_rate_rupees": 300}).status_code == 403
    r = council.put("/rates/plumbing", json={"hourly_rate_rupees": 300, "note": "GB resolution 12 Sep"})
    assert r.status_code == 200 and r.json()["hourly_rate_rupees"] == 300
    assert customer.get("/rates/quote?trade=plumbing&hours=2").json()["standard_rupees"] == 150 + 600


# ── settlement ───────────────────────────────────────────────────────────

def test_worker_proposes_customer_agrees_and_the_ledger_runs(customer, worker, council):
    booking_id = place_and_assign(customer, council, worker)
    assert customer.get(f"/bookings/{booking_id}/settlement").json() is None

    proposed = worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 2, "materials_rupees": 120, "work_note": "Replaced the tap washer"})
    assert proposed.status_code == 201, proposed.text
    s = proposed.json()
    assert s["status"] == "proposed" and s["waiting_on"] == "customer"
    assert s["standard_rupees"] == s["proposed_rupees"] == 150 + 2 * 250 + 120
    assert "visit" in s["explanation"]

    # the worker cannot answer their own proposal
    assert worker.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "agree"}).status_code == 409

    agreed = customer.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "agree", "paid_via": "upi"})
    assert agreed.status_code == 200, agreed.text
    s = agreed.json()
    assert s["status"] == "agreed" and s["agreed_rupees"] == 770 and s["paid_via"] == "upi" and s["waiting_on"] is None
    assert {e["party"]: e["amount_rupees"] for e in s["ledger"]} == {"worker": 654.5, "welfare_fund": 77.0, "platform_operations": 38.5}
    assert customer.get(f"/bookings/{booking_id}").json()["booking"]["status"] == "completed"
    # the worker's history carries it
    job = next(j for j in worker.get("/workers/me/jobs").json() if j["booking_id"] == booking_id)
    assert job["outcome"] == "completed" and job["settlement"]["status"] == "agreed" and job["billed_rupees"] == 770


def test_customer_counters_within_the_band_and_the_worker_accepts(customer, worker, council):
    booking_id = place_and_assign(customer, council, worker)
    worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1})  # ₹400 standard, band ₹300–₹500
    too_low = customer.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "counter", "amount_rupees": 200})
    assert too_low.status_code == 422 and "fair band" in too_low.json()["detail"]
    countered = customer.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "counter", "amount_rupees": 350, "note": "Took less than an hour"})
    assert countered.status_code == 200 and countered.json()["status"] == "countered" and countered.json()["waiting_on"] == "worker"
    # now it is the worker's turn, not the customer's
    assert customer.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "agree"}).status_code == 409
    agreed = worker.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "agree"})
    assert agreed.status_code == 200 and agreed.json()["agreed_rupees"] == 350
    assert council.get("/admin/dashboard").json()["money"]["gross_rupees"] == 350


def test_a_proposal_outside_the_band_is_refused(customer, worker, council):
    booking_id = place_and_assign(customer, council, worker)
    r = worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1, "amount_rupees": 900})
    assert r.status_code == 422 and "fair band" in r.json()["detail"]
    assert worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1, "amount_rupees": 480}).status_code == 201


def test_disagreement_goes_to_the_sabha_which_fixes_the_amount(customer, worker, council):
    booking_id = place_and_assign(customer, council, worker)
    worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 3})
    disputed = customer.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "dispute", "note": "He was here barely an hour"})
    assert disputed.status_code == 200 and disputed.json()["status"] == "disputed" and disputed.json()["waiting_on"] == "council"
    dispute_id = disputed.json()["dispute_id"]
    listed = council.get("/disputes?status=open").json()
    assert [d["id"] for d in listed] == [dispute_id]
    assert listed[0]["kind"] == "payment" and listed[0]["settlement_proposed_rupees"] == 900
    assert council.get("/admin/overview").json()["disputes"]["open"] == 1

    # nobody but the council can move it now
    assert worker.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "agree"}).status_code == 409
    assert customer.post(f"/bookings/{booking_id}/settlement/resolve", json={"amount_rupees": 500, "resolution": "x"}).status_code == 403

    resolved = council.post(f"/bookings/{booking_id}/settlement/resolve", json={"amount_rupees": 500, "resolution": "Both heard; 1.5 h at the card rate"})
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "agreed" and resolved.json()["agreed_rupees"] == 500
    assert council.get("/disputes?status=open").json() == []
    assert customer.get(f"/bookings/{booking_id}").json()["booking"]["status"] == "completed"


def test_only_the_parties_see_a_settlement(customer, worker, council, make_client):
    booking_id = place_and_assign(customer, council, worker)
    worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1})
    stranger = make_client("customer", name="Someone Else")
    assert stranger.get(f"/bookings/{booking_id}/settlement").status_code == 403
    assert stranger.post(f"/bookings/{booking_id}/settlement/respond", json={"action": "agree"}).status_code == 403
    other_worker = make_client("worker", name="Other Worker")
    assert other_worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1}).status_code in (403, 409)
    assert council.get(f"/bookings/{booking_id}/settlement").status_code == 200
    assert [s["booking_id"] for s in council.get("/settlements?status=open").json()] == [booking_id]


def test_a_price_needs_an_assigned_job(customer, worker, council):
    r = customer.post("/bookings", json={"customer_name": "H", "trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1]})
    booking_id = r.json()["id"]
    assert worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1}).status_code in (403, 409)


# ── live events ──────────────────────────────────────────────────────────

def test_writes_publish_events_the_client_can_poll(customer, worker, council):
    start = events.bus.latest
    booking_id = place_and_assign(customer, council, worker)
    worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1})
    got = council.get(f"/events?after={start}").json()
    assert [(e["topic"], e["action"]) for e in got] == [("bookings", "placed"), ("bookings", "assigned"), ("settlements", "proposed")]
    assert got[-1]["booking_id"] == booking_id
    # a failed write publishes nothing
    worker.post(f"/bookings/{booking_id}/settlement", json={"hours_worked": 1})
    assert len(council.get(f"/events?after={start}").json()) == 3
    assert customer.get("/events").status_code == 200


def test_the_event_stream_needs_a_session(client):
    assert client.get("/events").status_code == 401
