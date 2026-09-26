"""Phase A: cooperative federation tenant isolation."""
from __future__ import annotations

from app import cooperative as coop_mod
from app.cooperative import create_cooperative
from app.tenancy import tenant_id, set_tenant_id, reset_tenant_id
from app.repository import create_booking, create_worker, list_bookings, list_workers
from app.schemas import BookingCreate, WorkerCreate

DEFAULT_CODE = "SABHA-2026"


def _new_cooperative(name="Indore Urban Cooperative", code="SABHA-IN-002"):
    return create_cooperative(name=name, code=code, region="Indore")


def test_default_cooperative_exists(db_path):
    assert coop_mod.get_cooperative(cooperative_id=1).code == DEFAULT_CODE


def test_create_and_fetch_member_cooperative(db_path):
    c = _new_cooperative()
    fetched = coop_mod.get_cooperative(cooperative_id=c.id)
    assert fetched.id == c.id and fetched.code == "SABHA-IN-002" and c.id != 1


def test_list_cooperatives_includes_both(db_path):
    _new_cooperative()
    names = {c.code for c in coop_mod.list_cooperatives()}
    assert DEFAULT_CODE in names
    assert "SABHA-IN-002" in names


def test_tenant_id_defaults_to_one(db_path):
    assert tenant_id() == 1


def test_workers_are_scoped_per_cooperative(db_path):
    indore = _new_cooperative()

    token = set_tenant_id(1)
    r1 = create_worker(WorkerCreate(name="Bhopal Worker", trade="plumbing", phone="9000000200",
                                    latitude=23.2, longitude=77.4, locality="Bhopal"))
    assert r1.cooperative_id == 1
    assert any(w.id == r1.id for w in list_workers())

    set_tenant_id(indore.id)
    assert not any(w.id == r1.id for w in list_workers())

    reset_tenant_id(token)


def test_bookings_are_scoped_per_cooperative(db_path):
    indore = _new_cooperative()

    token = set_tenant_id(1)
    bk = create_booking(BookingCreate(customer_name="C1", trade="plumbing",
                                      latitude=23.2, longitude=77.4, address="x", customer_phone="9000000101"))
    assert bk.cooperative_id == 1
    assert any(b.id == bk.id for b in list_bookings())

    set_tenant_id(indore.id)
    assert not any(b.id == bk.id for b in list_bookings())

    reset_tenant_id(token)


def test_cross_tenant_access_returns_403(client, customer, db_path):
    # `customer` lives in the default cooperative (coop id 1). Requesting the API
    # to act as a different cooperative must be rejected by require_user.
    indore = _new_cooperative()
    bk = customer.post("/bookings", json={
        "customer_name": "C1", "trade": "plumbing", "latitude": 23.2, "longitude": 77.4,
        "address": "x", "customer_phone": "9000000101",
    })
    bid = bk.json()["id"]
    resp = customer.get(f"/bookings/{bid}", headers={"X-Cooperative-Id": str(indore.id)})
    assert resp.status_code == 403
