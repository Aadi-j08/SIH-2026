"""
Worker profile (Phase B): skills, certifications, portfolio and documents.

  GET    /workers/{id}/profile                              worker (own), council
  GET    /workers/{id}/skills                               worker (own), council
  POST   /workers/{id}/skills                               worker (own), council
  PATCH  /workers/{id}/skills/{skill_id}                    worker (own), council
  DELETE /workers/{id}/skills/{skill_id}                    worker (own), council
  GET    /workers/{id}/certifications                       worker (own), council
  POST   /workers/{id}/certifications                       worker (own), council
  PATCH  /workers/{id}/certifications/{cert_id}             worker (own), council
  DELETE /workers/{id}/certifications/{cert_id}             worker (own), council
  GET    /workers/{id}/portfolio                            worker (own), council
  POST   /workers/{id}/portfolio                            worker (own), council
  DELETE /workers/{id}/portfolio/{item_id}                  worker (own), council
  GET    /workers/{id}/documents                            worker (own), council
  POST   /workers/{id}/documents                            worker (own), council
  POST   /workers/{id}/verify/{table}/{item_id}             council only
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app import ownership, repository, profile
from app.auth import User, require_council, require_worker
from app.schemas import (
    CertificationCreate, SkillCreate, PortfolioItemCreate, WorkerDocumentCreate,
    VerificationRequest,
)

router = APIRouter(tags=["workers"])


def _resolve_worker(user: User, worker_id: int):
    """The worker record the caller may act on (own, or any for council); 404 if absent."""
    ownership.ensure_own_worker_record(user, worker_id)
    worker = repository.get_worker(worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
    return worker


# ── profile overview ────────────────────────────────────────────────────

@router.get("/workers/{worker_id}/profile", response_model=profile.ProfileSummary)
def profile_overview(worker_id: int, user: User = Depends(require_worker)) -> profile.ProfileSummary:
    _resolve_worker(user, worker_id)
    return profile.profile_summary(worker_id)


# ── skills ──────────────────────────────────────────────────────────────

@router.get("/workers/{worker_id}/skills", response_model=list[profile.SkillOut])
def list_skills(worker_id: int, user: User = Depends(require_worker)) -> list[profile.SkillOut]:
    _resolve_worker(user, worker_id)
    return profile.list_skills(worker_id)


@router.post("/workers/{worker_id}/skills", response_model=profile.SkillOut, status_code=201)
def add_skill(worker_id: int, body: SkillCreate, user: User = Depends(require_worker)) -> profile.SkillOut:
    _resolve_worker(user, worker_id)
    return profile.add_skill(worker_id, body.name, body.level)


@router.patch("/workers/{worker_id}/skills/{skill_id}", response_model=profile.SkillOut)
def edit_skill(worker_id: int, skill_id: int, body: SkillCreate, user: User = Depends(require_worker)) -> profile.SkillOut:
    _resolve_worker(user, worker_id)
    out = profile.update_skill(skill_id, worker_id, name=body.name, level=body.level)
    if out is None:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return out


@router.delete("/workers/{worker_id}/skills/{skill_id}", status_code=204)
def remove_skill(worker_id: int, skill_id: int, user: User = Depends(require_worker)) -> None:
    _resolve_worker(user, worker_id)
    if not profile.delete_skill(skill_id, worker_id):
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")


# ── certifications ──────────────────────────────────────────────────────

@router.get("/workers/{worker_id}/certifications", response_model=list[profile.CertificationOut])
def list_certifications(worker_id: int, user: User = Depends(require_worker)) -> list[profile.CertificationOut]:
    _resolve_worker(user, worker_id)
    return profile.list_certifications(worker_id)


@router.post("/workers/{worker_id}/certifications", response_model=profile.CertificationOut, status_code=201)
def add_certification(worker_id: int, body: CertificationCreate, user: User = Depends(require_worker)) -> profile.CertificationOut:
    _resolve_worker(user, worker_id)
    return profile.add_certification(
        worker_id, body.name, body.issuing_org, body.issue_date, body.expiry_date, body.document
    )


@router.patch("/workers/{worker_id}/certifications/{cert_id}", response_model=profile.CertificationOut)
def edit_certification(worker_id: int, cert_id: int, body: CertificationCreate, user: User = Depends(require_worker)) -> profile.CertificationOut:
    _resolve_worker(user, worker_id)
    out = profile.update_certification(
        cert_id, worker_id,
        name=body.name, issuing_org=body.issuing_org,
        issue_date=body.issue_date, expiry_date=body.expiry_date, document=body.document,
    )
    if out is None:
        raise HTTPException(status_code=404, detail=f"Certification {cert_id} not found")
    return out


@router.delete("/workers/{worker_id}/certifications/{cert_id}", status_code=204)
def remove_certification(worker_id: int, cert_id: int, user: User = Depends(require_worker)) -> None:
    _resolve_worker(user, worker_id)
    if not profile.delete_certification(cert_id, worker_id):
        raise HTTPException(status_code=404, detail=f"Certification {cert_id} not found")


# ── portfolio ──────────────────────────────────────────────────────────

@router.get("/workers/{worker_id}/portfolio", response_model=list[profile.PortfolioItemOut])
def list_portfolio(worker_id: int, user: User = Depends(require_worker)) -> list[profile.PortfolioItemOut]:
    _resolve_worker(user, worker_id)
    return profile.list_portfolio(worker_id)


@router.post("/workers/{worker_id}/portfolio", response_model=profile.PortfolioItemOut, status_code=201)
def add_portfolio_item(worker_id: int, body: PortfolioItemCreate, user: User = Depends(require_worker)) -> profile.PortfolioItemOut:
    _resolve_worker(user, worker_id)
    return profile.add_portfolio_item(worker_id, body.image_url, body.caption, body.category)


@router.delete("/workers/{worker_id}/portfolio/{item_id}", status_code=204)
def remove_portfolio_item(worker_id: int, item_id: int, user: User = Depends(require_worker)) -> None:
    _resolve_worker(user, worker_id)
    if not profile.delete_portfolio_item(item_id, worker_id):
        raise HTTPException(status_code=404, detail=f"Portfolio item {item_id} not found")


# ── documents ──────────────────────────────────────────────────────────

@router.get("/workers/{worker_id}/documents", response_model=list[profile.WorkerDocumentOut])
def list_documents(worker_id: int, user: User = Depends(require_worker)) -> list[profile.WorkerDocumentOut]:
    _resolve_worker(user, worker_id)
    return profile.list_documents(worker_id)


@router.post("/workers/{worker_id}/documents", response_model=profile.WorkerDocumentOut, status_code=201)
def add_document(worker_id: int, body: WorkerDocumentCreate, user: User = Depends(require_worker)) -> profile.WorkerDocumentOut:
    _resolve_worker(user, worker_id)
    return profile.add_document(worker_id, body.document_type, body.file_url)


# ── verification (council only) ─────────────────────────────────────────

@router.post("/workers/{worker_id}/verify/{table}/{item_id}", response_model=dict)
def verify_item(
    worker_id: int, table: str, item_id: int, body: VerificationRequest,
    user: User = Depends(require_council),
) -> dict:
    _resolve_worker(user, worker_id)
    if table not in ("skills", "certifications", "portfolio_items"):
        raise HTTPException(status_code=400, detail=f"cannot verify table '{table}'")
    if not profile.set_verification(table, item_id, body.verified, user.id):
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found in {table}")
    return {"verified": body.verified}
