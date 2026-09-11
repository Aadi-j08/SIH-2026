"""Per-portal accounts: sign-up, sign-in, sessions, and the walls between portals."""
from __future__ import annotations

from app import auth


def ghar(phone="98765 43210", **extra) -> dict:
    return {"portal": "ghar", "name": "Priya Sharma", "phone": phone, "password": "secret1", "locality": "Andheri East", **extra}


def kaam(phone="91234 56780", **extra) -> dict:
    return {"portal": "kaam", "name": "Asha Verma", "phone": phone, "password": "secret1", "trade": "Plumbing",
            "locality": "Andheri East", "languages": ["hi", "en"], **extra}


def sabha(phone="99887 76655", code="SABHA-2026", **extra) -> dict:
    return {"portal": "sabha", "name": "Rajesh Iyer", "phone": phone, "password": "secret12", "role": "Secretary",
            "council_code": code, **extra}


# ── sign-up ──────────────────────────────────────────────────────────────

def test_ghar_signup_creates_account_and_session(client):
    response = client.post("/auth/signup", json=ghar())
    assert response.status_code == 201, response.text
    user = response.json()["user"]
    assert user["portal"] == "ghar" and user["name"] == "Priya Sharma" and user["locality"] == "Andheri East"
    assert user["phone"] == "9876543210"                      # normalised
    assert "password_hash" not in user
    assert auth.SESSION_COOKIE in response.cookies

    assert client.get("/auth/me").json()["user"]["id"] == user["id"]


def test_kaam_signup_creates_the_worker_record(client):
    user = client.post("/auth/signup", json=kaam()).json()["user"]
    assert user["worker_id"] == 1 and user["languages"] == ["hi", "en"]

    worker = client.get("/workers/1").json()
    assert worker["name"] == "Asha Verma" and worker["trade"] == "plumbing" and worker["phone"] == "9123456780"
    assert (worker["latitude"], worker["longitude"]) == (auth.DEFAULT_LATITUDE, auth.DEFAULT_LONGITUDE)


def test_kaam_signup_needs_a_trade(client):
    assert client.post("/auth/signup", json=kaam(trade="")).status_code == 422
    assert client.get("/workers").json() == []


def test_sabha_signup_is_gated_by_the_council_code(client, monkeypatch):
    monkeypatch.setenv("SAHAKARSETU_COUNCIL_CODE", "COOP-42")
    assert client.post("/auth/signup", json=sabha(code="SABHA-2026")).status_code == 403
    assert client.post("/auth/signup", json=sabha(code="")).status_code == 422

    ok = client.post("/auth/signup", json=sabha(code="coop-42"))     # case-insensitive
    assert ok.status_code == 201, ok.text
    assert ok.json()["user"]["role"] == "Secretary"


def test_phone_must_be_ten_digits(client):
    assert client.post("/auth/signup", json=ghar(phone="12345")).status_code == 422
    assert client.post("/auth/signup", json=ghar(phone="+91 98765 43210")).status_code == 201
    assert client.post("/auth/signup", json=ghar(phone="098765 43210")).status_code == 409   # same number, normalised


def test_same_phone_one_account_per_portal(client):
    assert client.post("/auth/signup", json=ghar(phone="9000000001")).status_code == 201
    assert client.post("/auth/signup", json=ghar(phone="9000000001")).status_code == 409
    assert client.post("/auth/signup", json=kaam(phone="9000000001")).status_code == 201
    assert client.post("/auth/signup", json=sabha(phone="9000000001")).status_code == 201


# ── sign-in / sessions ───────────────────────────────────────────────────

def test_login_only_opens_the_portal_the_account_was_made_for(client):
    client.post("/auth/signup", json=ghar())
    client.post("/auth/logout")
    assert client.get("/auth/me").json()["user"] is None

    wrong_portal = client.post("/auth/login", json={"portal": "kaam", "phone": "9876543210", "password": "secret1"})
    assert wrong_portal.status_code == 401
    wrong_password = client.post("/auth/login", json={"portal": "ghar", "phone": "9876543210", "password": "nope"})
    assert wrong_password.status_code == 401

    ok = client.post("/auth/login", json={"portal": "ghar", "phone": "9876543210", "password": "secret1"})
    assert ok.status_code == 200 and ok.json()["user"]["portal"] == "ghar"
    assert client.get("/auth/me").json()["user"]["portal"] == "ghar"


def test_logout_ends_the_session(client):
    client.post("/auth/signup", json=ghar())
    token = client.cookies.get(auth.SESSION_COOKIE)
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").json()["user"] is None
    # even if the browser kept the cookie, the server no longer knows it
    client.cookies.set(auth.SESSION_COOKIE, token)
    assert client.get("/auth/me").json()["user"] is None


def test_password_hashing_round_trip():
    stored = auth.hash_password("hunter22")
    assert stored.startswith("pbkdf2_sha256$") and "hunter22" not in stored
    assert auth.verify_password("hunter22", stored)
    assert not auth.verify_password("hunter23", stored)
    assert not auth.verify_password("hunter22", "garbage")
