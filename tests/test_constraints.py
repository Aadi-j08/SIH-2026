"""Database integrity: constraints on fresh databases, triggers on old ones, and the API's clean 409s."""
from __future__ import annotations

import sqlite3

import pytest

from app import database

SITE = (23.18, 77.42)

LEGACY_SCHEMA = """
CREATE TABLE workers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, trade TEXT NOT NULL,
  latitude REAL NOT NULL, longitude REAL NOT NULL, jobs_this_week INTEGER NOT NULL DEFAULT 0, rating REAL,
  availability TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE bookings (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT NOT NULL, customer_phone TEXT,
  trade TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, address TEXT, scheduled_for TEXT,
  status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE assignments (id INTEGER PRIMARY KEY AUTOINCREMENT, booking_id INTEGER NOT NULL REFERENCES bookings(id),
  worker_id INTEGER NOT NULL REFERENCES workers(id), score REAL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
INSERT INTO workers (name, trade, latitude, longitude, jobs_this_week, rating) VALUES ('Asha', 'plumbing', 23.18, 77.42, 2, 4.8);
INSERT INTO bookings (customer_name, trade, latitude, longitude, status) VALUES ('Sharma', 'plumbing', 23.18, 77.42, 'assigned');
INSERT INTO assignments (booking_id, worker_id, score) VALUES (1, 1, 0.9);
"""

INVALID_WRITES = [
    ("unknown booking status", "UPDATE bookings SET status = 'lost' WHERE id = 1", "status must be"),
    ("negative jobs_this_week", "UPDATE workers SET jobs_this_week = -1 WHERE id = 1", "jobs_this_week"),
    ("rating above 5", "UPDATE workers SET rating = 7 WHERE id = 1", "rating"),
    ("rating below 1", "UPDATE workers SET rating = 0.5 WHERE id = 1", "rating"),
    ("second assignment for a booking", "INSERT INTO assignments (booking_id, worker_id) VALUES (1, 1)", "assignment"),
]


def seed_via_api(council):
    council.post("/workers", json={"name": "Asha", "trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1]})
    booking_id = council.post("/bookings", json={"customer_name": "Sharma", "trade": "plumbing", "latitude": SITE[0], "longitude": SITE[1]}).json()["id"]
    assert council.post(f"/bookings/{booking_id}/assign").status_code == 200
    return booking_id


@pytest.mark.parametrize("label, sql, expected_message", INVALID_WRITES)
def test_fresh_database_rejects_invalid_values(council, label, sql, expected_message):
    seed_via_api(council)
    with database.connection() as conn:
        with pytest.raises(sqlite3.IntegrityError) as raised:
            conn.execute(sql)
        assert expected_message.lower() in str(raised.value).lower(), label


def test_valid_values_are_accepted(council):
    seed_via_api(council)
    with database.connection() as conn:
        conn.execute("UPDATE workers SET jobs_this_week = 0, rating = 1 WHERE id = 1")
        conn.execute("UPDATE workers SET rating = 5 WHERE id = 1")
        conn.execute("UPDATE workers SET rating = NULL WHERE id = 1")
        for status in database.BOOKING_STATUSES:
            conn.execute("UPDATE bookings SET status = ? WHERE id = 1", (status,))


@pytest.mark.parametrize("label, sql, expected_message", INVALID_WRITES)
def test_legacy_database_is_migrated_in_place_and_then_enforces_the_rules(tmp_path, monkeypatch, label, sql, expected_message):
    legacy = tmp_path / "legacy.db"
    raw = sqlite3.connect(legacy)
    raw.executescript(LEGACY_SCHEMA)
    raw.commit()
    raw.close()
    monkeypatch.setattr(database, "DB_PATH", legacy)

    database.init_db()          # migrates
    database.init_db()          # and is idempotent

    with database.connection() as conn:
        assert [r["version"] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")] == [1, 2]
        # nothing was dropped or altered
        assert conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM assignments").fetchone()[0] == 1
        assert dict(conn.execute("SELECT name, jobs_this_week, rating FROM workers").fetchone()) == {"name": "Asha", "jobs_this_week": 2, "rating": 4.8}
        assert "customer_user_id" in {r["name"] for r in conn.execute("PRAGMA table_info(bookings)")}
        with pytest.raises(sqlite3.IntegrityError) as raised:
            conn.execute(sql)
        assert expected_message.lower() in str(raised.value).lower(), label


def test_duplicate_assignment_is_rejected_by_the_api_with_a_clean_409(council):
    booking_id = seed_via_api(council)

    second = council.post(f"/bookings/{booking_id}/assign")

    assert second.status_code == 409
    assert "only pending bookings can be assigned" in second.json()["detail"]
    with database.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM assignments WHERE booking_id = ?", (booking_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT jobs_this_week FROM workers WHERE id = 1").fetchone()[0] == 1   # not double-counted


def test_race_that_slips_past_the_status_check_still_cannot_double_assign(council, monkeypatch):
    """Even if a second request saw the booking as pending, the database refuses the second assignment row."""
    from app.services import booking_flow

    booking_id = seed_via_api(council)
    with database.connection() as conn:
        conn.execute("UPDATE bookings SET status = 'pending' WHERE id = ?", (booking_id,))   # simulate the stale read

    response = council.post(f"/bookings/{booking_id}/assign")

    assert response.status_code == 409
    assert response.json()["detail"] == "booking already has an assignment"
    with database.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM assignments WHERE booking_id = ?", (booking_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT status FROM bookings WHERE id = ?", (booking_id,)).fetchone()[0] == "pending"  # rolled back together
    assert booking_flow.ASSIGNED == "assigned"


def test_no_eligible_worker_is_a_clean_409(council):
    booking_id = council.post("/bookings", json={"customer_name": "X", "trade": "carpentry", "latitude": SITE[0], "longitude": SITE[1]}).json()["id"]
    response = council.post(f"/bookings/{booking_id}/assign")
    assert response.status_code == 409
    assert response.json()["detail"] == f"No eligible worker found for booking {booking_id}"


def test_list_bookings_rejects_unknown_status_filter(council):
    assert council.get("/bookings", params={"status": "lost"}).status_code == 422
    assert council.get("/bookings", params={"status": "cancelled"}).status_code == 200
