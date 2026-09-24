"""Shared fixtures: every test gets a fresh SQLite file, an anonymous TestClient, and signed-in clients per role."""
from __future__ import annotations

import itertools
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app

COUNCIL_CODE = "SABHA-2026"
_phones = itertools.count(9_100_000_000)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    # Tests always run on a throwaway SQLite file, even if the developer's
    # shell exports DATABASE_URL (see app/database.py use_postgres()).
    monkeypatch.setattr(database, "DATABASE_URL", None)
    path = tmp_path / "sahakarsetu_test.db"
    monkeypatch.setattr(database, "DB_PATH", path)
    monkeypatch.setenv("SAHAKARSETU_DB", str(path))
    monkeypatch.setenv("SAHAKARSETU_COUNCIL_CODE", COUNCIL_CODE)
    # Auto-assign is on by default in production; tests drive the manual /assign
    # flow themselves unless a test opts back in (see test_auto_assign_*).
    monkeypatch.setattr("app.main.AUTO_ASSIGN_ON_CREATE", False)
    database.init_db()
    return path


@pytest.fixture
def client(db_path):
    """Anonymous client (no session)."""
    with TestClient(app) as test_client:
        yield test_client


def signup_body(role: str, *, name: str | None = None, phone: str | None = None, trade: str = "plumbing",
                locality: str | None = None, **extra) -> dict:
    portal = {"customer": "ghar", "worker": "kaam", "council": "sabha"}[role]
    body = {
        "portal": portal,
        "name": name or {"customer": "Priya Sharma", "worker": "Asha Verma", "council": "Council Secretary"}[role],
        "phone": phone or str(next(_phones)),
        "password": "secret12",
        "locality": locality,
    }
    if role == "worker":
        body["trade"] = trade
    if role == "council":
        body.update({"role": "secretary", "council_code": COUNCIL_CODE})
    body.update(extra)
    return body


@pytest.fixture
def make_client(db_path) -> Callable[..., TestClient]:
    """Factory: `make_client("worker", trade="electrical")` → a TestClient signed in as a fresh account of that role.

    The signed-in user is available as `client.user` and the API token as `client.token`.
    """
    clients: list[TestClient] = []

    def _make(role: str = "council", approved: bool = True, **kwargs) -> TestClient:
        test_client = TestClient(app)
        test_client.__enter__()
        clients.append(test_client)
        response = test_client.post("/auth/signup", json=signup_body(role, **kwargs))
        assert response.status_code == 201, response.text
        body = response.json()
        if role == "worker" and approved:
            # New Kaam sign-ups wait for council approval; most tests want a worker the engine can use.
            with database.connection() as conn:
                conn.execute("UPDATE workers SET status = 'active' WHERE id = ?", (body["user"]["worker_id"],))
        test_client.user = body["user"]          # type: ignore[attr-defined]
        test_client.token = body["session_token"]  # type: ignore[attr-defined]
        return test_client

    yield _make
    for test_client in clients:
        test_client.__exit__(None, None, None)


@pytest.fixture
def council(make_client) -> TestClient:
    return make_client("council")


@pytest.fixture
def customer(make_client) -> TestClient:
    return make_client("customer")


@pytest.fixture
def worker(make_client) -> TestClient:
    return make_client("worker")
