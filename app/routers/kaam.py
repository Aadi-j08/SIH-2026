"""
Kaam — the worker's own endpoints.

  GET    /workers/me/summary                       worker: the numbers on their home page
  GET    /workers/me/jobs                          worker: assigned / completed / passed-on jobs with money and ratings
  PUT    /workers/{id}/availability                worker (own record), council: replace the windows
  PATCH  /workers/{id}/availability/{index}        worker (own record), council: change one window's time or free/busy
  DELETE /workers/{id}/availability/{index}        worker (own record), council: remove one window
  POST   /bookings/{id}/accept                     worker assigned to it, council
  POST   /bookings/{id}/decline                    worker assigned to it, council: pass it on; goes to the next-best worker
  GET    /workers/pending                          council: sign-ups waiting for approval
  POST   /workers/{id}/approve                     council
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app import kaam, ownership
from app.auth import User, require_council, require_worker
from app.schemas import Worker
from app import tenancy

log = logging.getLogger("sahakarsetu.kaam")
router = APIRouter(tags=["kaam"])


def _own_worker_id(user: User) -> int:
    if user.worker_id is None:
        raise HTTPException(status_code=403, detail="This account is not linked to a worker record. Ask the cooperative to fix it.")
    return user.worker_id


def _call(fn, *args):
    try:
        return fn(*args)
    except kaam.KaamError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


# ── the worker's own view ────────────────────────────────────────────────

@router.get("/workers/me/summary", response_model=kaam.WorkerSummary)
def my_summary(user: User = Depends(require_worker)) -> kaam.WorkerSummary:
    return _call(kaam.summary, _own_worker_id(user))


@router.get("/workers/me/jobs", response_model=list[kaam.WorkerJob])
def my_jobs(user: User = Depends(require_worker)) -> list[kaam.WorkerJob]:
    return _call(kaam.jobs, _own_worker_id(user))


# ── availability edits ───────────────────────────────────────────────────

@router.put("/workers/{worker_id}/availability", response_model=Worker)
def replace_availability(worker_id: int, body: kaam.AvailabilityUpdate, user: User = Depends(require_worker)) -> Worker:
    ownership.ensure_own_worker_record(user, worker_id)
    return _call(kaam.replace_availability, worker_id, body.windows)


@router.patch("/workers/{worker_id}/availability/{index}", response_model=Worker)
def patch_window(worker_id: int, index: int, body: kaam.WindowPatch, user: User = Depends(require_worker)) -> Worker:
    ownership.ensure_own_worker_record(user, worker_id)
    return _call(kaam.patch_window, worker_id, index, body)


@router.delete("/workers/{worker_id}/availability/{index}", response_model=Worker)
def remove_window(worker_id: int, index: int, user: User = Depends(require_worker)) -> Worker:
    ownership.ensure_own_worker_record(user, worker_id)
    return _call(kaam.remove_window, worker_id, index)


# ── replying to a job ────────────────────────────────────────────────────

def _acting_worker_id(user: User, booking_id: int) -> int:
    """The worker replying: the signed-in worker, or (for the council) whoever the booking is assigned to."""
    if not user.is_council:
        return _own_worker_id(user)
    from app.booking_flow_db import booking_flow_connection

    with booking_flow_connection() as conn:
        row = conn.execute(
            "SELECT worker_id FROM assignments WHERE booking_id = ? AND cooperative_id = ? ORDER BY id DESC LIMIT 1",
            (booking_id, tenancy.tenant_id()),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=409, detail=f"Booking {booking_id} has no assignment to reply to")
    return row["worker_id"]


@router.post("/bookings/{booking_id}/accept", response_model=kaam.ReplyResult)
def accept_job(booking_id: int, user: User = Depends(require_worker)) -> kaam.ReplyResult:
    return _call(kaam.accept, booking_id, _acting_worker_id(user, booking_id))


@router.post("/bookings/{booking_id}/start", response_model=kaam.ReplyResult)
def start_job(
    booking_id: int,
    body: kaam.StartWorkRequest | None = None,
    user: User = Depends(require_worker),
) -> kaam.ReplyResult:
    """Worker uploads on-site arrival selfie and transitions booking to 'in_progress'."""
    selfie = body.start_selfie_url if body else None
    return _call(kaam.start_work, booking_id, _acting_worker_id(user, booking_id), selfie)


@router.post("/bookings/{booking_id}/photo-proof")
def save_photo_proof(
    booking_id: int,
    body: kaam.ProofOfWorkRequest,
    user: User = Depends(require_worker),
) -> dict:
    """Records start arrival selfie or completion proof photo."""
    return _call(
        kaam.record_proof_of_work,
        booking_id,
        _acting_worker_id(user, booking_id),
        body.start_selfie_url,
        body.end_photo_url,
    )


@router.post("/bookings/{booking_id}/verify-repair")
def verify_repair_ai(
    booking_id: int,
    body: kaam.ProofOfWorkRequest,
    user: User = Depends(require_worker),
) -> dict:
    """AI Vision analysis of start damage and completion photos via Gemini 1.5 Flash Vision."""
    from app.services.vision_verifier import verify_repair_photos
    from app.database import connection

    with connection() as conn:
        row = conn.execute("SELECT trade, customer_notes FROM bookings WHERE id = ? AND cooperative_id = ?", (booking_id, tenancy.tenant_id())).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
        trade = row["trade"]
        notes = row["customer_notes"]

    return verify_repair_photos(
        trade=trade,
        start_photo_data=body.start_selfie_url,
        end_photo_data=body.end_photo_url,
        job_notes=notes,
    )


@router.post("/bookings/{booking_id}/decline", response_model=kaam.ReplyResult)
def decline_job(booking_id: int, body: kaam.DeclineRequest, user: User = Depends(require_worker)) -> kaam.ReplyResult:
    worker_id = _acting_worker_id(user, booking_id)
    result = _call(kaam.decline, booking_id, worker_id, body)
    log.info("booking %s declined by worker %s (%s) -> %s", booking_id, worker_id, body.reason,
             result.reassigned_to or "pending")
    return result


# ── council approval ─────────────────────────────────────────────────────

@router.get("/workers/pending", response_model=list[Worker])
def pending_workers(_: User = Depends(require_council)) -> list[Worker]:
    return kaam.pending_workers()


@router.post("/workers/{worker_id}/approve", response_model=Worker)
def approve_worker(worker_id: int, user: User = Depends(require_council)) -> Worker:
    worker = _call(kaam.approve, worker_id)
    log.info("worker %s approved by council #%s", worker_id, user.id)
    return worker
