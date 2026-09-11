"""Shared fixtures: every test gets a fresh SQLite file and a TestClient bound to it."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "sahakarsetu_test.db"
    monkeypatch.setattr(database, "DB_PATH", path)
    monkeypatch.setenv("SAHAKARSETU_DB", str(path))
    database.init_db()
    return path


@pytest.fixture
def client(db_path):
    with TestClient(app) as test_client:
        yield test_client
