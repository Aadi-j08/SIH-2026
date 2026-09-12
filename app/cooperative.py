"""
The cooperative's own record: who it is, where it operates, how it governs
itself, and the two policies the Sabha dashboard applies everywhere — the
weekly job limit per worker (workload %, "nearing limit" warnings) and how
the welfare fund is allocated (the fund pie). One row; created with sensible
defaults the first time it is asked for, edited from the Sabha profile page.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.database import connection

DEFAULT_FUND_ALLOCATION: dict[str, int] = {
    "Worker welfare": 40,
    "Training & skill development": 25,
    "Emergency assistance": 20,
    "Operations": 15,
}

DEFAULTS: dict[str, Any] = {
    "name": "Bhopal Urban Services Cooperative",
    "short_name": "Bhopal Central Cooperative",
    "registration_id": "SABHA-MP-0417",
    "established": 2026,
    "area": "Bhopal",
    "radius_km": 12,
    "verified": 1,
    "worker_kyc": 1,
    "payments_verified": 1,
    "secretary": None,
    "coordinator": None,
    "last_meeting": "2026-09-04",
    "weekly_job_limit": 6,
    "fund_allocation": json.dumps(DEFAULT_FUND_ALLOCATION),
}


class Cooperative(BaseModel):
    name: str
    short_name: str
    registration_id: str | None = None
    established: int | None = None
    area: str | None = None
    radius_km: float | None = None
    verified: bool = False
    worker_kyc: bool = False
    payments_verified: bool = False
    secretary: str | None = None
    coordinator: str | None = None
    last_meeting: str | None = None
    weekly_job_limit: int = 6
    fund_allocation: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_FUND_ALLOCATION))
    updated_at: str | None = None


class CooperativeUpdate(BaseModel):
    """Every field optional: send only what changed."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    short_name: str | None = Field(default=None, min_length=1, max_length=80)
    registration_id: str | None = Field(default=None, max_length=40)
    established: int | None = Field(default=None, ge=1900, le=2100)
    area: str | None = Field(default=None, max_length=120)
    radius_km: float | None = Field(default=None, gt=0, le=500)
    verified: bool | None = None
    worker_kyc: bool | None = None
    payments_verified: bool | None = None
    secretary: str | None = Field(default=None, max_length=80)
    coordinator: str | None = Field(default=None, max_length=80)
    last_meeting: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    weekly_job_limit: int | None = Field(default=None, ge=1, le=50)
    fund_allocation: dict[str, int] | None = None

    @field_validator("fund_allocation")
    @classmethod
    def _sums_to_100(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is None:
            return None
        if not value or any(p < 0 for p in value.values()):
            raise ValueError("fund allocation needs at least one category with a non-negative percent")
        if sum(value.values()) != 100:
            raise ValueError("fund allocation percentages must add up to 100")
        return value


def _model(row: sqlite3.Row) -> Cooperative:
    data = dict(row)
    data.pop("id", None)
    for flag in ("verified", "worker_kyc", "payments_verified"):
        data[flag] = bool(data.get(flag))
    data["fund_allocation"] = json.loads(data.get("fund_allocation") or "{}") or dict(DEFAULT_FUND_ALLOCATION)
    return Cooperative.model_validate(data)


def _ensure_row(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM cooperative WHERE id = 1").fetchone()
    if row is None:
        columns = ", ".join(DEFAULTS)
        marks = ", ".join("?" for _ in DEFAULTS)
        conn.execute(f"INSERT INTO cooperative (id, {columns}) VALUES (1, {marks})", tuple(DEFAULTS.values()))
        row = conn.execute("SELECT * FROM cooperative WHERE id = 1").fetchone()
    return row


def get_cooperative(conn: sqlite3.Connection | None = None) -> Cooperative:
    if conn is not None:
        return _model(_ensure_row(conn))
    with connection() as own:
        return _model(_ensure_row(own))


def update_cooperative(data: CooperativeUpdate) -> Cooperative:
    changes = data.model_dump(exclude_none=True)
    if "fund_allocation" in changes:
        changes["fund_allocation"] = json.dumps(changes["fund_allocation"])
    for flag in ("verified", "worker_kyc", "payments_verified"):
        if flag in changes:
            changes[flag] = int(changes[flag])
    with connection() as conn:
        _ensure_row(conn)
        if changes:
            assignments = ", ".join(f"{column} = ?" for column in changes)
            conn.execute(
                f"UPDATE cooperative SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                tuple(changes.values()),
            )
        return _model(conn.execute("SELECT * FROM cooperative WHERE id = 1").fetchone())
