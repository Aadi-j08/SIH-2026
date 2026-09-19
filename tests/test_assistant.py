"""Assistant intent, confirmation, fallback, and permission tests."""
from datetime import date


def test_english_read_only_status_requires_booking_id(customer):
    created = customer.post("/bookings", json={
        "customer_name": "Priya", "trade": "plumbing", "latitude": 23.18, "longitude": 77.42,
    })
    booking_id = created.json()["id"]
    response = customer.post("/assistant/message", json={"transcript": f"check booking {booking_id} status"})
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "en"
    assert body["intent"] == "check_booking_status"
    assert body["entities"]["booking_id"] == booking_id


def test_hinglish_availability_requires_confirmation(worker):
    response = worker.post("/assistant/voice", json={"transcript": "kal subah plumbing ke liye free hoon"})
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "hi-Latn"
    assert body["intent"] == "set_availability"
    assert body["requires_confirmation"] is True
    assert body["action_preview"]["type"] == "set_availability"


def test_hindi_availability_is_understood(worker):
    response = worker.post("/assistant/message", json={"transcript": "मैं कल सुबह खाली हूँ"})
    assert response.status_code == 200
    assert response.json()["language"] == "hi"
    assert response.json()["intent"] == "set_availability"


def test_missing_time_asks_for_clarification(worker):
    response = worker.post("/assistant/message", json={"transcript": "tomorrow I am available"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "set_availability"
    assert "start time" in body["reply"]


def test_missing_date_asks_for_clarification(worker):
    response = worker.post("/assistant/message", json={"transcript": "I am free at 10"})
    assert response.status_code == 200
    assert "date" in response.json()["reply"]


def test_unknown_trade_is_not_guessed(customer):
    response = customer.post("/assistant/message", json={"transcript": "book a zorp service tomorrow at 10 in Bhopal"})
    assert response.status_code == 200
    body = response.json()
    assert body["entities"].get("trade") is None
    assert body["confidence"] < 0.85


def test_low_confidence_falls_back(customer):
    response = customer.post("/assistant/message", json={"transcript": "xyzzy"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "unknown"
    assert body["confidence"] < 0.60
    assert "repeat" in body["reply"].lower()


def test_worker_cannot_use_customer_booking_tool(worker):
    response = worker.post("/assistant/message", json={"transcript": "book a plumber tomorrow at 10 in Bhopal"})
    assert response.status_code == 403


def test_customer_booking_is_previewed_then_requires_location_coordinates(customer):
    transcript = "book plumbing tomorrow at 10 in Bhopal"
    preview = customer.post("/assistant/message", json={"transcript": transcript, "reference_date": date(2026, 9, 18).isoformat()})
    assert preview.status_code == 200
    body = preview.json()
    assert body["intent"] == "create_booking"
    assert body["requires_confirmation"] is True
    assert body["action_preview"]["type"] == "create_booking"


def test_confirmed_customer_booking_dispatches_and_is_audited(make_client, customer, db_path):
    worker = make_client("worker", name="Asha")
    transcript = "book plumbing tomorrow at 10 in Bhopal"
    preview = customer.post("/assistant/message", json={"transcript": transcript})
    assert preview.json()["requires_confirmation"] is True
    executed = customer.post("/assistant/message", json={
        "transcript": transcript, "confirmed": True, "latitude": 23.18, "longitude": 77.42,
    })
    assert executed.status_code == 200, executed.text
    result = executed.json()["result"]
    assert result["booking"]["trade"] == "plumbing"
    assert result["assignment"]["worker"]["id"] == worker.user["worker_id"]
    from app.database import connection
    with connection() as conn:
        audit = conn.execute("SELECT outcome FROM assistant_audit WHERE intent = 'create_booking' ORDER BY id DESC LIMIT 1").fetchone()
    assert audit["outcome"] == "executed"


def test_customer_cannot_read_another_customers_booking(make_client, customer):
    other = make_client("customer", name="Other Household")
    created = other.post("/bookings", json={"customer_name": "Other", "trade": "plumbing", "latitude": 23.18, "longitude": 77.42})
    booking_id = created.json()["id"]
    response = customer.post("/assistant/message", json={"transcript": f"check booking {booking_id} status"})
    assert response.status_code == 403


def test_invalid_intent_and_fallback_are_safe(customer):
    response = customer.post("/assistant/message", json={"transcript": "please do something mysterious"})
    assert response.status_code == 200
    assert response.json()["action_preview"] == {}


def test_languages_endpoint_requires_auth(client, customer):
    assert client.get("/assistant/languages").status_code == 401
    assert customer.get("/assistant/languages").json()[0]["code"] == "en"
