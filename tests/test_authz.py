"""Roles and ownership: who may read, change and assign what."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

SITE = (23.18, 77.42)


def booking_payload(**extra) -> dict:
    return {"customer_name": "Test Household", "trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1],
            "scheduled_for": "2026-09-12T10:00", **extra}


def place_booking(client) -> int:
    response = client.post("/bookings", json=booking_payload())
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ── identifying the caller ───────────────────────────────────────────────

def test_anonymous_requests_are_refused_with_401(client):
    assert client.post("/bookings", json=booking_payload()).status_code == 401
    assert client.get("/bookings/1").status_code == 401
    assert client.get("/admin/dashboard").status_code == 401
    assert client.post("/bookings/1/assign").status_code == 401
    assert client.get("/workers").status_code == 401
    assert client.get("/forecast?trade=plumbing").status_code == 401


def test_me_reports_the_access_role(customer, worker, council):
    assert customer.get("/auth/me").json()["access_role"] == "customer"
    assert worker.get("/auth/me").json()["access_role"] == "worker"
    assert council.get("/auth/me").json()["access_role"] == "council"
    assert council.get("/auth/me").json()["user"]["access_role"] == "council"


def test_bearer_token_identifies_the_user_without_a_cookie(client, council):
    """API clients (Swagger, curl) can send the session token as a Bearer header."""
    headers = {"Authorization": f"Bearer {council.token}"}
    assert client.get("/auth/me").json()["user"] is None
    assert client.get("/auth/me", headers=headers).json()["user"]["id"] == council.user["id"]
    assert client.get("/admin/dashboard", headers=headers).status_code == 200
    assert client.get("/admin/dashboard", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


# ── customers ────────────────────────────────────────────────────────────

def test_customer_cannot_view_another_customers_booking(make_client, council):
    priya, rahul = make_client("customer", name="Priya"), make_client("customer", name="Rahul")
    booking_id = place_booking(priya)

    assert priya.get(f"/bookings/{booking_id}").status_code == 200
    denied = rahul.get(f"/bookings/{booking_id}")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "This booking is not yours to view"
    assert council.get(f"/bookings/{booking_id}").status_code == 200   # council sees everything


def test_customer_only_lists_their_own_bookings(make_client, council):
    priya, rahul = make_client("customer", name="Priya"), make_client("customer", name="Rahul")
    mine = place_booking(priya)
    place_booking(rahul)
    assert [b["id"] for b in priya.get("/bookings").json()] == [mine]
    assert len(council.get("/bookings").json()) == 2


def test_customer_cannot_rate_another_customers_booking(make_client, worker, council):
    priya, rahul = make_client("customer", name="Priya"), make_client("customer", name="Rahul")
    booking_id = place_booking(priya)
    assert council.post(f"/bookings/{booking_id}/assign").status_code == 200
    assert worker.post(f"/bookings/{booking_id}/complete", json={"amount": 500}).status_code == 200

    assert rahul.post(f"/bookings/{booking_id}/rating", json={"rating": 5}).status_code == 403
    assert priya.post(f"/bookings/{booking_id}/rating", json={"rating": 5}).status_code == 200


def test_customer_cannot_assign_or_see_council_pages(customer, council):
    booking_id = place_booking(customer)
    denied = customer.post(f"/bookings/{booking_id}/assign")
    assert denied.status_code == 403
    assert "council" in denied.json()["detail"]
    assert customer.get("/admin/dashboard").status_code == 403
    assert customer.get(f"/bookings/{booking_id}/recommendations").status_code == 403
    assert customer.post("/workers", json={"name": "X", "trade": "plumbing", "latitude": 0, "longitude": 0}).status_code == 403
    assert customer.get("/workers").status_code == 403
    assert customer.get("/forecast?trade=plumbing").status_code == 403
    # the booking is still pending: nothing was assigned by the refused call
    assert council.get(f"/bookings/{booking_id}").json()["booking"]["status"] == "pending"


# ── workers ──────────────────────────────────────────────────────────────

def test_worker_cannot_modify_another_workers_availability(make_client):
    asha, ravi = make_client("worker", name="Asha"), make_client("worker", name="Ravi")
    payload = {"transcript": "kal subah free hoon", "reference_date": "2026-09-11"}

    denied = asha.post(f"/workers/{ravi.user['worker_id']}/availability/voice", json=payload)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "You can only update your own availability"
    assert asha.post(f"/workers/{asha.user['worker_id']}/availability/voice", json=payload).status_code == 200
    assert ravi.get(f"/workers/{ravi.user['worker_id']}").json()["availability"] == []   # untouched
    assert asha.get(f"/workers/{ravi.user['worker_id']}").status_code == 403           # nor readable


def test_worker_cannot_complete_another_workers_assignment(make_client, customer, council):
    asha, ravi = make_client("worker", name="Asha"), make_client("worker", name="Ravi")
    booking_id = place_booking(customer)
    assigned_to = council.post(f"/bookings/{booking_id}/assign").json()["worker"]["id"]
    chosen, other = (asha, ravi) if assigned_to == asha.user["worker_id"] else (ravi, asha)

    denied = other.post(f"/bookings/{booking_id}/complete", json={"amount": 500})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "This job is assigned to another worker"
    assert other.get(f"/bookings/{booking_id}").status_code == 403
    assert chosen.get(f"/bookings/{booking_id}").status_code == 200
    assert chosen.post(f"/bookings/{booking_id}/complete", json={"amount": 500}).status_code == 200


def test_worker_lists_only_bookings_assigned_to_them(make_client, customer, council):
    asha = make_client("worker", name="Asha")
    make_client("worker", name="Ravi")
    first, second = place_booking(customer), place_booking(customer)
    council.post(f"/bookings/{first}/assign")     # Asha and Ravi tie on every factor: lower id (Asha) wins
    council.post(f"/bookings/{second}/assign")    # Asha now has a job this week, so fairness picks Ravi

    mine = [b["id"] for b in asha.get("/bookings").json()]
    assert mine == [first]
    assert [b["id"] for b in asha.get("/bookings?status=assigned").json()] == [first]


def test_worker_and_customer_cannot_use_council_endpoints(worker, customer):
    for c in (worker, customer):
        assert c.get("/admin/dashboard").status_code == 403
        assert c.post("/bookings/1/assign").status_code == 403
    assert worker.post("/bookings", json=booking_payload()).status_code == 403
    assert customer.post("/bookings/1/complete", json={"amount": 100}).status_code == 403


# ── council ──────────────────────────────────────────────────────────────

def test_council_can_act_on_behalf_of_everyone(council, customer, worker):
    booking_id = place_booking(customer)
    assert council.post(f"/bookings/{booking_id}/assign").status_code == 200
    assert council.post(f"/bookings/{booking_id}/complete", json={"amount": 450}).status_code == 200
    assert council.post(f"/bookings/{booking_id}/rating", json={"rating": 4}).status_code == 200
    assert council.post(f"/workers/{worker.user['worker_id']}/availability/voice",
                        json={"transcript": "roz subah"}).status_code == 200
    assert council.get("/admin/dashboard").json()["bookings"]["completed"] == 1


def test_bookings_placed_by_council_still_record_who_placed_them(council):
    booking_id = place_booking(council)
    assert council.get(f"/bookings/{booking_id}").json()["booking"]["customer_user_id"] == council.user["id"]


def test_public_stats_need_no_login(client, council, customer):
    place_booking(customer)
    stats = client.get("/stats")
    assert stats.status_code == 200
    assert stats.json() == {"workers": 0, "bookings_completed": 0, "welfare_fund_rupees": 0.0, "average_rating": None}


def test_unexpected_errors_are_not_leaked(council, monkeypatch):
    from app.services import booking_flow

    def explode(*_args):
        raise RuntimeError("secret internal detail: table xyz")

    monkeypatch.setattr(booking_flow, "admin_dashboard", explode)
    with TestClient(app, raise_server_exceptions=False, cookies=council.cookies) as quiet:
        response = quiet.get("/admin/dashboard")
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our side. Please try again."}
    assert "xyz" not in response.text
