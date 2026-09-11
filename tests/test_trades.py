"""Canonical trade names: aliases collapse to one word for storage, matching and filtering."""
from __future__ import annotations

import pytest

from app.trades import CANONICAL_TRADES, canonical_trade

SITE = (23.18, 77.42)


@pytest.mark.parametrize("alias, canonical", [
    ("plumber", "plumbing"), ("Plumbing", "plumbing"), ("pipe repair", "plumbing"), ("  Pipe-Repair ", "plumbing"),
    ("electrician", "electrical"), ("electrical", "electrical"), ("wiring", "electrical"), ("Electrical work", "electrical"),
    ("carpenter", "carpentry"), ("carpentry", "carpentry"), ("Woodwork", "carpentry"),
    ("painter", "painting"), ("painting", "painting"),
    ("cleaner", "cleaning"), ("cleaning", "cleaning"), ("house cleaning", "cleaning"),
    ("plumbing services", "plumbing"), ("electrician needed", "electrical"),
])
def test_aliases_normalise(alias, canonical):
    assert canonical_trade(alias) == canonical
    assert canonical in CANONICAL_TRADES


def test_unknown_trades_pass_through_cleaned_not_rejected():
    assert canonical_trade("  Welding ") == "welding"
    assert canonical_trade("AC repair") == "ac repair"


def test_workers_and_bookings_are_stored_with_the_canonical_trade(council, make_client):
    worker = council.post("/workers", json={"name": "Meena", "trade": "Electrician", "latitude": SITE[0], "longitude": SITE[1]})
    assert worker.status_code == 201 and worker.json()["trade"] == "electrical"

    signed_up = make_client("worker", name="Imran", trade="Pipe repair")     # sign-up goes through the same contract
    assert council.get(f"/workers/{signed_up.user['worker_id']}").json()["trade"] == "plumbing"

    booking = council.post("/bookings", json={"customer_name": "X", "trade": "wiring", "latitude": SITE[0], "longitude": SITE[1]})
    assert booking.status_code == 201 and booking.json()["trade"] == "electrical"


def test_matching_and_filters_work_across_aliases(council):
    council.post("/workers", json={"name": "Meena", "trade": "Electrician", "latitude": SITE[0], "longitude": SITE[1]})
    booking_id = council.post("/bookings", json={"customer_name": "X", "trade": "wiring", "latitude": SITE[0], "longitude": SITE[1]}).json()["id"]

    ranked = council.get(f"/bookings/{booking_id}/recommendations").json()
    assert [r["worker_name"] for r in ranked] == ["Meena"]
    assert [w["name"] for w in council.get("/workers", params={"trade": "electrician"}).json()] == ["Meena"]
    assert [b["id"] for b in council.get("/bookings", params={"trade": "Electrical work"}).json()] == [booking_id]
    assert council.get("/forecast", params={"trade": "electrician"}).json()["trade"] == "electrical"
