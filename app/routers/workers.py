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
  POST   /workers/{id}/documents/upload                     worker (own), council
  GET    /documents/{id}/file                               owning worker, council
  POST   /documents/{id}/verify                             council only
  POST   /workers/{id}/verify/{table}/{item_id}             council only
"""
from __future__ import annotations

from typing import get_args

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app import ownership, repository, profile, uploads
from app.auth import User, require_council, require_user, require_worker
from app.schemas import (
    CertificationCreate, SkillCreate, PortfolioItemCreate, WorkerDocumentCreate,
    DocumentType, DocumentVerificationRequest, VerificationRequest,
)

router = APIRouter(tags=["workers"])

# DocumentType is a Literal alias; the upload endpoint needs the runtime set.
DOCUMENT_TYPES = frozenset(get_args(DocumentType))


def _resolve_worker(user: User, worker_id: int):
    """The worker record the caller may act on (own, or any for council); 404 if absent."""
    ownership.ensure_own_worker_record(user, worker_id)
    worker = repository.get_worker(worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
    return worker


def _resolve_document(user: User, document_id: int):
    """The worker document the council may review. 404 if absent or outside the caller's tenant."""
    from app.database import connection
    from app import tenancy
    with connection() as conn:
        row = conn.execute(
            # Explicit columns: the callers only need worker_id and the
            # verification fields, and `content` is megabytes of ID scan.
            "SELECT id, worker_id, document_type, file_url, uploaded_at, cooperative_id, "
            "verified, verified_by, verified_at, rejection_reason, "
            "filename, content_type, byte_size, content IS NOT NULL AS has_content "
            "FROM worker_documents WHERE id = ? AND cooperative_id = ?",
            (document_id, tenancy.tenant_id()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return row


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


@router.post("/workers/{worker_id}/documents/upload", response_model=profile.WorkerDocumentOut, status_code=201)
async def upload_document(
    worker_id: int,
    file: UploadFile = File(..., description="A PDF, JPG or PNG of the document"),
    document_type: str = Form("aadhaar"),
    user: User = Depends(require_worker),
) -> profile.WorkerDocumentOut:
    """Upload a document's bytes. This is what Kaam onboarding uses to satisfy the
    council's Aadhaar requirement; POST /workers/{id}/documents remains for callers
    that only hold an off-FS reference.

    The bytes are read once, capped, and validated by app.uploads — the browser's
    Content-Type is never trusted.
    """
    _resolve_worker(user, worker_id)
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail=f"document_type must be one of {sorted(DOCUMENT_TYPES)}")
    if len(profile.list_documents(worker_id)) >= uploads.max_files():
        cap = uploads.max_files()
        raise HTTPException(
            status_code=409,
            detail=(
                f"You can keep at most {cap} document{'s' if cap != 1 else ''}. "
                "Remove one before adding another."
            ),
        )

    limit = uploads.max_bytes()
    data = await file.read(limit + 1)
    try:
        # file.size is only used to phrase the oversize message; the accept/refuse
        # decision is made on the bytes actually read above.
        safe_name, content_type, file_url = uploads.validate_upload(file.filename, data, file.size)
    except uploads.UploadRejected as exc:
        # 415: the client sent something this endpoint cannot accept.
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    return profile.add_document_upload(
        worker_id, document_type, safe_name, content_type, data, file_url
    )


@router.get("/documents/{document_id}/file")
def download_document(document_id: int, user: User = Depends(require_user)) -> Response:
    """Stream a stored upload back. Only the owning worker or the council may read it;
    the document is served with a neutral Content-Type and as an attachment, so an
    uploaded HTML/SVG-ish file can never execute against the app's origin."""
    row = _resolve_document(user, document_id)
    _resolve_worker(user, row["worker_id"])
    stored = profile.document_content(document_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="This document has no stored file, only a reference")
    data, content_type, filename = stored
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/documents/{document_id}/verify", response_model=profile.WorkerDocumentOut)
def verify_document(
    document_id: int, body: DocumentVerificationRequest,
    user: User = Depends(require_council),
) -> profile.WorkerDocumentOut:
    """Council review of a worker-uploaded document. Workers upload; council only
    verifies (or rejects with a reason, or re-opens for correction)."""
    row = _resolve_document(user, document_id)
    worker_id = row["worker_id"]
    _resolve_worker(user, worker_id)
    if not profile.set_document_verification(document_id, body.verified, user.id, body.rejection_reason):
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    docs = profile.list_documents(worker_id)
    for d in docs:
        if d.id == document_id:
            return d
    raise HTTPException(status_code=404, detail=f"Document {document_id} not found")


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
