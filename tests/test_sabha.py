"""Sabha endpoints: cooperative profile, overview, customers, auto-allocation, disputes."""
from __future__ import annotations

import datetime as dt

from app import database

SITE = (23.18, 77.42)


def booking(trade="plumbing", lat=SITE[0], lon=SITE[1]) -> dict:
    return {"customer_name": "Test Household", "trade": trade, "latitude": lat, "longitude": lon}


def backdate(table: str, row_id: int, hours: float, column: str = "created_at") -> None:
    when = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    with database.connection() as conn:
        conn.execute(f"UPDATE {table} SET {column} = ? WHERE id = ?", (when, row_id))


# ── cooperative profile ──────────────────────────────────────────────────

def test_cooperative_profile_has_defaults_and_is_editable(council, customer):
    profile = customer.get("/cooperative").json()          # any signed-in user may read it
    assert profile["name"] == "Bhopal Urban Services Cooperative"
    assert profile["weekly_job_limit"] == 6
    assert sum(profile["fund_allocation"].values()) == 100

    assert customer.put("/cooperative", json={"secretary": "X"}).status_code == 403
    updated = council.put("/cooperative", json={"secretary": "Rajesh Iyer", "weekly_job_limit": 5,
                                                "fund_allocation": {"Worker welfare": 60, "Operations": 40}}).json()
    assert updated["secretary"] == "Rajesh Iyer" and updated["weekly_job_limit"] == 5
    assert updated["fund_allocation"] == {"Worker welfare": 60, "Operations": 40}
    assert council.get("/cooperative").json()["secretary"] == "Rajesh Iyer"


def test_fund_allocation_must_sum_to_100(council):
    assert council.put("/cooperative", json={"fund_allocation": {"a": 50, "b": 40}}).status_code == 422


# ── overview ─────────────────────────────────────────────────────────────

def test_overview_on_an_empty_cooperative(council):
    body = council.get("/admin/overview").json()
    assert body["metrics"]["demands"] == {"active": 0, "unassigned": 0, "ongoing": 0, "completed_today": 0}
    assert body["metrics"]["fairness"]["index"] == 100
    assert body["attention"] == [] and body["matching"] == []
    assert body["cooperative"]["members"] == 1                 # the council account itself


def test_overview_reflects_demand_workforce_and_attention(council, customer, make_client):
    asha = make_client("worker", name="Asha Verma", trade="plumbing")
    meena = make_client("worker", name="Meena Devi", trade="electrical")
    old = customer.post("/bookings", json=booking("plumbing")).json()
    customer.post("/bookings", json=booking("plumbing"))
    customer.post("/bookings", json=booking("electrical"))
    backdate("bookings", old["id"], hours=3)

    body = council.get("/admin/overview").json()
    assert body["metrics"]["demands"] == {"active": 3, "unassigned": 3, "ongoing": 0, "completed_today": 0}
    assert body["metrics"]["workers"]["registered"] == 2 and body["metrics"]["workers"]["available_now"] == 2

    rows = {t["trade"]: t for t in body["trades"]}
    assert rows["plumbing"]["unassigned"] == 2 and rows["plumbing"]["available_workers"] == 1
    assert rows["plumbing"]["status"] == "needs_workers"        # one worker for two open demands
    assert rows["electrical"]["status"] == "good"

    kinds = {a["kind"]: a for a in body["attention"]}
    assert kinds["assign"]["count"] == 1 and kinds["assign"]["level"] == "red"
    assert "opportunity" in kinds

    match = {m["trade"]: m for m in body["matching"]}
    assert match["plumbing"]["booking_id"] == old["id"] and match["plumbing"]["booking_age_minutes"] >= 179
    assert [s["name"] for s in match["plumbing"]["suggestions"]] == ["Asha Verma"]
    assert [s["name"] for s in match["electrical"]["suggestions"]] == ["Meena Devi"]
    assert asha.user["worker_id"] and meena.user["worker_id"]


def test_overview_counts_money_and_disputes(council, customer, make_client):
    worker = make_client("worker", name="Asha Verma", trade="plumbing")
    b = customer.post("/bookings", json=booking()).json()
    assert council.post(f"/bookings/{b['id']}/assign").status_code == 200
    assert worker.post(f"/bookings/{b['id']}/complete", json={"amount": 1000}).status_code == 200
    assert customer.post("/disputes", json={"booking_id": b["id"], "kind": "payment", "amount_rupees": 450}).status_code == 201

    body = council.get("/admin/overview").json()
    assert body["metrics"]["earnings"]["this_month_rupees"] == 850
    assert body["metrics"]["fund"]["total_rupees"] == 100
    assert body["metrics"]["demands"]["completed_today"] == 1
    assert body["performance"]["jobs_completed"] == 1 and body["performance"]["workers_benefited"] == 1
    assert body["performance"]["avg_response_minutes"] is not None
    assert body["disputes"]["open"] == 1 and body["disputes"]["recent"][0]["amount_rupees"] == 450
    assert any(a["kind"] == "disputes" for a in body["attention"])


# ── customers ────────────────────────────────────────────────────────────

def test_customers_list_with_booking_counts(council, customer):
    customer.post("/bookings", json=booking())
    customer.post("/bookings", json=booking())
    rows = council.get("/admin/customers").json()
    assert len(rows) == 1 and rows[0]["name"] == "Priya Sharma" and rows[0]["bookings"] == 2
    assert customer.get("/admin/customers").status_code == 403


# ── auto-allocation ──────────────────────────────────────────────────────

def test_auto_allocate_assigns_pending_bookings_with_explanations(council, customer, make_client):
    make_client("worker", name="Asha Verma", trade="plumbing")
    make_client("worker", name="Ravi Kumar", trade="plumbing")
    make_client("worker", name="Meena Devi", trade="electrical")
    ids = [customer.post("/bookings", json=booking("plumbing")).json()["id"] for _ in range(2)]
    other = customer.post("/bookings", json=booking("electrical")).json()["id"]

    result = council.post("/allocation/auto", params={"trade": "Plumbers"}).json()
    assert result["trade"] == "plumbing" and result["attempted"] == 2 and result["skipped"] == []
    assert [a["booking_id"] for a in result["assigned"]] == ids
    assert {a["worker_name"] for a in result["assigned"]} == {"Asha Verma", "Ravi Kumar"}   # fairness spreads them
    assert all(a["explanation"] for a in result["assigned"])
    assert council.get(f"/bookings/{other}").json()["booking"]["status"] == "pending"

    rest = council.post("/allocation/auto").json()
    assert rest["attempted"] == 1 and rest["assigned"][0]["booking_id"] == other
    assert council.get("/admin/overview").json()["metrics"]["demands"]["unassigned"] == 0


def test_auto_allocate_skips_bookings_nobody_can_take(council, customer):
    customer.post("/bookings", json=booking("carpentry"))
    result = council.post("/allocation/auto").json()
    assert result["attempted"] == 1 and result["assigned"] == [] and len(result["skipped"]) == 1


# ── disputes ─────────────────────────────────────────────────────────────

def test_dispute_lifecycle(council, customer, make_client):
    worker = make_client("worker", name="Asha Verma", trade="plumbing")
    stranger = make_client("customer", name="Someone Else")
    b = customer.post("/bookings", json=booking()).json()
    council.post(f"/bookings/{b['id']}/assign")
    worker.post(f"/bookings/{b['id']}/complete", json={"amount": 800})

    assert stranger.post("/disputes", json={"booking_id": b["id"], "kind": "quality"}).status_code == 403
    raised = customer.post("/disputes", json={"booking_id": b["id"], "kind": "quality", "description": "Leak came back"})
    assert raised.status_code == 201, raised.text
    d = raised.json()
    assert d["raised_by"] == "customer" and d["label"] == "Service quality complaint"
    assert d["worker_name"] == "Asha Verma" and d["status"] == "open"
    assert customer.post("/disputes", json={"booking_id": b["id"], "kind": "payment"}).status_code == 409   # one open at a time

    assert customer.get("/disputes").status_code == 403
    assert [x["id"] for x in council.get("/disputes", params={"status": "open"}).json()] == [d["id"]]

    resolved = council.post(f"/disputes/{d['id']}/resolve", json={"resolution": "Worker revisited; fixed free of charge"}).json()
    assert resolved["status"] == "resolved" and resolved["resolved_at"]
    assert council.post(f"/disputes/{d['id']}/resolve", json={"resolution": "again"}).status_code == 409
    assert council.get("/admin/overview").json()["disputes"] | {"open": 0, "resolved": 1} == council.get("/admin/overview").json()["disputes"]


def test_worker_can_dispute_only_their_own_assignment(council, customer, make_client):
    worker = make_client("worker", name="Asha Verma", trade="plumbing")
    other = make_client("worker", name="Ravi Kumar", trade="plumbing")
    b = customer.post("/bookings", json=booking()).json()
    council.post(f"/bookings/{b['id']}/assign")
    assigned_to = council.get(f"/bookings/{b['id']}").json()["assignment"]["worker"]["id"]
    mine, theirs = (worker, other) if assigned_to == worker.user["worker_id"] else (other, worker)
    assert theirs.post("/disputes", json={"booking_id": b["id"], "kind": "payment", "amount_rupees": 200}).status_code == 403
    assert mine.post("/disputes", json={"booking_id": b["id"], "kind": "payment", "amount_rupees": 200}).status_code == 201
