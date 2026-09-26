"""
Phase B — provider profile data access: skills, certifications, portfolio and
worker documents. Every query is scoped to the current tenant (see
app/tenancy.py) so a council user from one cooperative can't reach another's
provider records.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field

from app import tenancy
from app.database import connection

VerifyTarget = Literal["skills", "certifications", "portfolio_items"]


class SkillOut(BaseModel):
    id: int
    worker_id: int
    name: str
    level: str
    verified: bool
    verified_by: int | None
    verified_at: str | None
    cooperative_id: int
    created_at: str | None


class CertificationOut(BaseModel):
    id: int
    worker_id: int
    name: str
    issuing_org: str | None
    issue_date: str | None
    expiry_date: str | None
    document: str | None
    verified: bool
    verified_by: int | None
    verified_at: str | None
    cooperative_id: int
    created_at: str | None


class PortfolioItemOut(BaseModel):
    id: int
    worker_id: int
    image_url: str
    caption: str | None
    category: str | None
    verified: bool
    verified_by: int | None
    verified_at: str | None
    cooperative_id: int
    created_at: str | None


class WorkerDocumentOut(BaseModel):
    id: int
    worker_id: int
    document_type: str
    file_url: str
    uploaded_at: str | None
    cooperative_id: int


class ProfileSummary(BaseModel):
    worker_id: int
    skills: list[SkillOut] = Field(default_factory=list)
    certifications: list[CertificationOut] = Field(default_factory=list)
    portfolio: list[PortfolioItemOut] = Field(default_factory=list)
    documents: list[WorkerDocumentOut] = Field(default_factory=list)
    completeness: float = 0.0  # 0..1 how much of the profile is filled in


# ── skills ───────────────────────────────────────────────────────────────

def list_skills(worker_id: int) -> list[SkillOut]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM worker_skills WHERE worker_id = ? AND cooperative_id = ? ORDER BY verified DESC, id",
            (worker_id, tenancy.tenant_id()),
        )
        return [_skill(row) for row in rows]


def add_skill(worker_id: int, name: str, level: str = "intermediate") -> SkillOut:
    with connection() as conn:
        conn.execute(
            "INSERT INTO worker_skills (worker_id, skill, level, cooperative_id) VALUES (?, ?, ?, ?)",
            (worker_id, name, level, tenancy.tenant_id()),
        )
        row = conn.execute(
            "SELECT * FROM worker_skills WHERE worker_id = ? AND skill = ? ORDER BY id DESC LIMIT 1",
            (worker_id, name),
        ).fetchone()
        return _skill(row)


def update_skill(skill_id: int, worker_id: int, *, name: str | None = None, level: str | None = None) -> SkillOut | None:
    cid = tenancy.tenant_id()
    cols, params = [], []
    if name is not None:
        cols.append("skill = ?"); params.append(name)
    if level is not None:
        cols.append("level = ?"); params.append(level)
    if not cols:
        with connection() as conn:
            row = conn.execute(
                "SELECT * FROM worker_skills WHERE id = ? AND cooperative_id = ?",
                (skill_id, cid),
            ).fetchone()
            return _skill(row) if row else None
    params += [worker_id, cid, skill_id]
    with connection() as conn:
        conn.execute(
            f"UPDATE worker_skills SET {', '.join(cols)} WHERE id = ? AND worker_id = ? AND cooperative_id = ?",
            (*params[:len(cols)], worker_id, cid, skill_id),
        )
        row = conn.execute(
            "SELECT * FROM worker_skills WHERE id = ? AND cooperative_id = ?",
            (skill_id, cid),
        ).fetchone()
        return _skill(row) if row else None


def delete_skill(skill_id: int, worker_id: int) -> bool:
    cid = tenancy.tenant_id()
    with connection() as conn:
        cur = conn.execute(
            "DELETE FROM worker_skills WHERE id = ? AND worker_id = ? AND cooperative_id = ?",
            (skill_id, worker_id, cid),
        )
        return cur.rowcount > 0


# ── certifications ───────────────────────────────────────────────────────

def list_certifications(worker_id: int) -> list[CertificationOut]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM certifications WHERE worker_id = ? AND cooperative_id = ? ORDER BY verified DESC, id",
            (worker_id, tenancy.tenant_id()),
        )
        return [_cert(row) for row in rows]


def add_certification(
    worker_id: int,
    name: str,
    issuing_org: str | None = None,
    issue_date: str | None = None,
    expiry_date: str | None = None,
    document: str | None = None,
) -> CertificationOut:
    with connection() as conn:
        conn.execute(
            "INSERT INTO certifications (worker_id, name, issuing_org, issue_date, expiry_date, document, cooperative_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (worker_id, name, issuing_org, issue_date, expiry_date, document, tenancy.tenant_id()),
        )
        return _latest_cert(conn, worker_id, name)


def update_certification(cert_id: int, worker_id: int, **fields) -> CertificationOut | None:
    cid = tenancy.tenant_id()
    allowed = {"name", "issuing_org", "issue_date", "expiry_date", "document"}
    cols, params = [], []
    for k in allowed:
        if k in fields and fields[k] is not None:
            cols.append(f"{k} = ?"); params.append(fields[k])
    if not cols:
        with connection() as conn:
            return _cert_row(conn, cert_id)
    params += [worker_id, cid, cert_id]
    with connection() as conn:
        conn.execute(
            f"UPDATE certifications SET {', '.join(cols)} WHERE id = ? AND worker_id = ? AND cooperative_id = ?",
            (*params[:len(cols)], worker_id, cid, cert_id),
        )
        row = conn.execute(
            "SELECT * FROM certifications WHERE id = ? AND cooperative_id = ?",
            (cert_id, cid),
        ).fetchone()
        return _cert(row) if row else None


def delete_certification(cert_id: int, worker_id: int) -> bool:
    with connection() as conn:
        cur = conn.execute(
            "DELETE FROM certifications WHERE id = ? AND worker_id = ? AND cooperative_id = ?",
            (cert_id, worker_id, tenancy.tenant_id()),
        )
        return cur.rowcount > 0


# ── portfolio ────────────────────────────────────────────────────────────

def list_portfolio(worker_id: int) -> list[PortfolioItemOut]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM portfolio_items WHERE worker_id = ? AND cooperative_id = ? ORDER BY id DESC",
            (worker_id, tenancy.tenant_id()),
        )
        return [_portfolio(row) for row in rows]


def add_portfolio_item(
    worker_id: int, image_url: str, caption: str | None = None, category: str | None = None
) -> PortfolioItemOut:
    with connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_items (worker_id, image_url, caption, category, cooperative_id) VALUES (?, ?, ?, ?, ?)",
            (worker_id, image_url, caption, category, tenancy.tenant_id()),
        )
        row = conn.execute(
            "SELECT * FROM portfolio_items WHERE worker_id = ? AND cooperative_id = ? ORDER BY id DESC LIMIT 1",
            (worker_id, tenancy.tenant_id()),
        ).fetchone()
        return _portfolio(row)


def delete_portfolio_item(item_id: int, worker_id: int) -> bool:
    with connection() as conn:
        cur = conn.execute(
            "DELETE FROM portfolio_items WHERE id = ? AND worker_id = ? AND cooperative_id = ?",
            (item_id, worker_id, tenancy.tenant_id()),
        )
        return cur.rowcount > 0


# ── documents ────────────────────────────────────────────────────────────

def list_documents(worker_id: int) -> list[WorkerDocumentOut]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM worker_documents WHERE worker_id = ? AND cooperative_id = ? ORDER BY id",
            (worker_id, tenancy.tenant_id()),
        )
        return [_doc(row) for row in rows]


def add_document(worker_id: int, document_type: str, file_url: str) -> WorkerDocumentOut:
    with connection() as conn:
        conn.execute(
            "INSERT INTO worker_documents (worker_id, document_type, file_url, cooperative_id) VALUES (?, ?, ?, ?)",
            (worker_id, document_type, file_url, tenancy.tenant_id()),
        )
        row = conn.execute(
            "SELECT * FROM worker_documents WHERE worker_id = ? AND cooperative_id = ? ORDER BY id DESC LIMIT 1",
            (worker_id, tenancy.tenant_id()),
        ).fetchone()
        return _doc(row)


# ── verification (council) ────────────────────────────────────────────────

def set_verification(table: str, item_id: int, verified: bool, verified_by: int | None) -> bool:
    allowed = {"skills": "worker_skills", "certifications": "certifications", "portfolio_items": "portfolio_items"}
    if table not in allowed:
        raise ValueError(f"unknown verification target: {table}")
    sql_table = allowed[table]
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(sep=" ", timespec="seconds")
    with connection() as conn:
        cur = conn.execute(
            f"UPDATE {sql_table} SET verified = ?, verified_by = ?, verified_at = ? "
            "WHERE id = ? AND cooperative_id = ?",
            (int(bool(verified)), verified_by, now if verified else None, item_id, tenancy.tenant_id()),
        )
        return cur.rowcount > 0


def profile_summary(worker_id: int) -> ProfileSummary:
    cid = tenancy.tenant_id()
    with connection() as conn:
        skills = [_skill(r) for r in conn.execute(
            "SELECT * FROM worker_skills WHERE worker_id = ? AND cooperative_id = ?", (worker_id, cid))]
        certs = [_cert(r) for r in conn.execute(
            "SELECT * FROM certifications WHERE worker_id = ? AND cooperative_id = ?", (worker_id, cid))]
        portfolio = [_portfolio(r) for r in conn.execute(
            "SELECT * FROM portfolio_items WHERE worker_id = ? AND cooperative_id = ?", (worker_id, cid))]
        docs = [_doc(r) for r in conn.execute(
            "SELECT * FROM worker_documents WHERE worker_id = ? AND cooperative_id = ?", (worker_id, cid))]

    filled = sum([
        bool(skills), bool(certs), bool(portfolio), bool(docs),
        any(s.verified for s in skills),
        any(c.verified for c in certs),
    ])
    return ProfileSummary(
        worker_id=worker_id, skills=skills, certifications=certs,
        portfolio=portfolio, documents=docs,
        completeness=round(min(filled / 7.0, 1.0), 2),
    )


# ── row mappers ───────────────────────────────────────────────────────────

def _skill(row: sqlite3.Row) -> SkillOut:
    d = dict(row)
    d["verified"] = bool(d["verified"])
    d["name"] = d.pop("skill")
    return SkillOut.model_validate(d)


def _cert(row: sqlite3.Row) -> CertificationOut:
    d = dict(row)
    d["verified"] = bool(d["verified"])
    return CertificationOut.model_validate(d)


def _portfolio(row: sqlite3.Row) -> PortfolioItemOut:
    d = dict(row)
    d["verified"] = bool(d["verified"])
    return PortfolioItemOut.model_validate(d)


def _doc(row: sqlite3.Row) -> WorkerDocumentOut:
    d = dict(row)
    return WorkerDocumentOut.model_validate(d)


def _skill_row(conn: sqlite3.Connection, skill_id: int) -> SkillOut | None:
    row = conn.execute("SELECT * FROM worker_skills WHERE id = ?", (skill_id,)).fetchone()
    return _skill(row) if row else None


def _cert_row(conn: sqlite3.Connection, cert_id: int) -> CertificationOut | None:
    row = conn.execute("SELECT * FROM certifications WHERE id = ?", (cert_id,)).fetchone()
    return _cert(row) if row else None


def _latest_skill(conn: sqlite3.Connection, worker_id: int, name: str) -> SkillOut:
    row = conn.execute(
        "SELECT * FROM worker_skills WHERE worker_id = ? AND skill = ? ORDER BY id DESC LIMIT 1",
        (worker_id, name),
    ).fetchone()
    return _skill(row)


def _latest_cert(conn: sqlite3.Connection, worker_id: int, name: str) -> CertificationOut:
    row = conn.execute(
        "SELECT * FROM certifications WHERE worker_id = ? AND name = ? ORDER BY id DESC LIMIT 1",
        (worker_id, name),
    ).fetchone()
    return _cert(row)
