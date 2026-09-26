"""
Phase E — welfare, insurance and grievances.

  GET  /benefits            council: list all benefits (optionally ?worker_id=)
  POST /benefits            council: register a benefit for a worker
  GET  /insurance-policies  council: list policies
  POST /insurance-policies  council: add a policy
  GET  /grievances          council: list all grievances
  POST /grievances          any worker (kaam) or council: raise a grievance
  PATCH /grievances/{id}    council: update status/resolution
"""
from __future__ import annotations

import datetime as dt
import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app import tenancy
from app.auth import User, require_council, require_user, require_worker
from app.schemas import (
    Benefit, BenefitCreate, Grievance, GrievanceCreate, GrievanceStatusUpdate,
    InsurancePolicy, InsurancePolicyCreate,
)
from app.booking_flow_db import booking_flow_connection

log = logging.getLogger("sahakarsetu.welfare")
router = APIRouter(tags=["welfare"])

_BOOL = {"true": 1, "false": 0, "": 0}


def _bool(v) -> int:
    return _BOOL.get(str(v).strip().lower(), int(bool(v))) if not isinstance(v, bool) else int(v)


@router.get("/benefits", response_model=list[Benefit])
def list_benefits(worker_id: int | None = None, _: User = Depends(require_council)) -> list[Benefit]:
    cid = tenancy.tenant_id()
    sql = "SELECT * FROM benefits WHERE cooperative_id = ?"
    params: list = [cid]
    if worker_id is not None:
        sql += " AND worker_id = ?"
        params.append(worker_id)
    sql += " ORDER BY id DESC"
    with booking_flow_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Benefit.model_validate(_normalize_benefit(r)) for r in rows]


@router.post("/benefits", response_model=Benefit)
def add_benefit(body: BenefitCreate, _: User = Depends(require_council)) -> Benefit:
    with booking_flow_connection() as conn:
        # verify worker belongs to this cooperative
        exists = conn.execute("SELECT 1 FROM workers WHERE id = ? AND cooperative_id = ?", (body.worker_id, tenancy.tenant_id())).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Worker {body.worker_id} not found")
        conn.execute(
            "INSERT INTO benefits (worker_id, kind, name, description, eligible, claimed, amount_rupees, "
            "start_date, end_date, document, cooperative_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.worker_id, body.kind, body.name, body.description, _bool(body.eligible), _bool(body.claimed),
             body.amount_rupees, body.start_date, body.end_date, body.document, tenancy.tenant_id()),
        )
    return _last_benefit(body.worker_id, body.name)


@router.get("/insurance-policies", response_model=list[InsurancePolicy])
def list_policies(active_only: bool = True, _: User = Depends(require_council)) -> list[InsurancePolicy]:
    sql = "SELECT * FROM insurance_policies WHERE cooperative_id = ?"
    params = [tenancy.tenant_id()]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY id DESC"
    with booking_flow_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [InsurancePolicy.model_validate(_normalize_policy(r)) for r in rows]


@router.post("/insurance-policies", response_model=InsurancePolicy)
def add_policy(body: InsurancePolicyCreate, _: User = Depends(require_council)) -> InsurancePolicy:
    with booking_flow_connection() as conn:
        conn.execute(
            "INSERT INTO insurance_policies (name, kind, insurer, policy_number, premium_rupees, premium_paid, "
            "coverage_paise, start_date, end_date, active, cooperative_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.name, body.kind, body.insurer, body.policy_number, body.premium_rupees, _bool(body.premium_paid),
             body.coverage_paise, body.start_date, body.end_date, _bool(body.active), tenancy.tenant_id()),
        )
    return _last_policy(body.name)


@router.get("/grievances", response_model=list[Grievance])
def list_grievances(status: str | None = None, _: User = Depends(require_council)) -> list[Grievance]:
    sql = "SELECT * FROM grievances WHERE cooperative_id = ?"
    params: list = [tenancy.tenant_id()]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    with booking_flow_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Grievance.model_validate(_normalize_grievance(r)) for r in rows]


@router.post("/grievances", response_model=Grievance)
def raise_grievance(body: GrievanceCreate, user: User = Depends(require_user)) -> Grievance:
    worker_id = body.worker_id or user.worker_id
    if worker_id and not user.is_council:
        # a worker can only raise for themselves
        if user.worker_id != worker_id:
            raise HTTPException(status_code=403, detail="You can only raise a grievance for your own worker record.")
    with booking_flow_connection() as conn:
        cur = conn.execute(
            "INSERT INTO grievances (worker_id, raised_by_user_id, kind, title, description, priority, cooperative_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (worker_id, user.id, body.kind, body.title, body.description, body.priority, tenancy.tenant_id()),
        )
        gid = cur.lastrowid
        return _grievance_by_id(conn, gid)


@router.patch("/grievances/{grievance_id}", response_model=Grievance)
def update_grievance(grievance_id: int, body: GrievanceStatusUpdate, _: User = Depends(require_council)) -> Grievance:
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
    with booking_flow_connection() as conn:
        cur = conn.execute(
            "UPDATE grievances SET status = ?, resolution = COALESCE(?, resolution), updated_at = ? "
            "WHERE id = ? AND cooperative_id = ?",
            (body.status, body.resolution, now, grievance_id, tenancy.tenant_id()),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Grievance {grievance_id} not found")
        return _grievance_by_id(conn, grievance_id)


def _last_benefit(worker_id: int, name: str) -> Benefit:
    with booking_flow_connection() as conn:
        row = conn.execute(
            "SELECT * FROM benefits WHERE worker_id = ? AND name = ? ORDER BY id DESC LIMIT 1",
            (worker_id, name),
        ).fetchone()
        return Benefit.model_validate(_normalize_benefit(row))


def _last_policy(name: str) -> InsurancePolicy:
    with booking_flow_connection() as conn:
        row = conn.execute(
            "SELECT * FROM insurance_policies WHERE name = ? ORDER BY id DESC LIMIT 1", (name,)
        ).fetchone()
        return InsurancePolicy.model_validate(_normalize_policy(row))


def _grievance_by_id(conn: sqlite3.Connection, gid: int) -> Grievance:
    row = conn.execute("SELECT * FROM grievances WHERE id = ? AND cooperative_id = ?", (gid, tenancy.tenant_id())).fetchone()
    return Grievance.model_validate(_normalize_grievance(row))


def _normalize_benefit(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["eligible"] = bool(d.get("eligible"))
    d["claimed"] = bool(d.get("claimed"))
    return d


def _normalize_policy(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["premium_paid"] = bool(d.get("premium_paid"))
    d["active"] = bool(d.get("active"))
    return d


def _normalize_grievance(row: sqlite3.Row) -> dict:
    return dict(row)
