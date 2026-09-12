"""
Disputes — the cooperative as neutral mediator.

A customer or worker raises a dispute on a booking they are party to
(payment amount, service quality, anything else); the council reviews and
resolves it with a note. Nothing here touches the ledger: a resolution is
a recorded decision, and any money movement stays a council action.
"""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.auth import User
from app.database import connection

Kind = Literal["payment", "quality", "other"]
Party = Literal["customer", "worker", "council"]

KIND_LABEL: dict[str, str] = {"payment": "Payment dispute", "quality": "Service quality complaint", "other": "Other"}


class DisputeCreate(BaseModel):
    booking_id: int
    kind: Kind
    description: str | None = Field(default=None, max_length=1000)
    amount_rupees: Decimal | None = Field(default=None, ge=0, le=10_000_000, description="Amount in question, for payment disputes")


class DisputeResolve(BaseModel):
    resolution: str = Field(min_length=1, max_length=1000)


class Dispute(BaseModel):
    id: int
    booking_id: int
    kind: Kind
    label: str
    raised_by: Party
    raised_by_user_id: int | None = None
    raised_by_name: str | None = None
    amount_rupees: float | None = None
    description: str | None = None
    status: Literal["open", "resolved"]
    resolution: str | None = None
    created_at: str
    resolved_at: str | None = None
    # context from the booking, for the resolution centre
    trade: str | None = None
    customer_name: str | None = None
    worker_name: str | None = None


class DisputeStats(BaseModel):
    open: int
    resolved: int
    resolution_rate: float | None = Field(description="resolved / total, 0..1; None when there are none")


class DisputeError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


_SELECT = """
    SELECT d.*, u.name AS raised_by_name, b.trade, b.customer_name, w.name AS worker_name
    FROM disputes d
    JOIN bookings b ON b.id = d.booking_id
    LEFT JOIN users u ON u.id = d.raised_by_user_id
    LEFT JOIN assignments a ON a.booking_id = b.id
    LEFT JOIN workers w ON w.id = a.worker_id
"""


def _model(row: sqlite3.Row) -> Dispute:
    data: dict[str, Any] = dict(row)
    paise = data.pop("amount_paise", None)
    data["amount_rupees"] = round(paise / 100, 2) if paise is not None else None
    data["label"] = KIND_LABEL.get(data["kind"], "Dispute")
    return Dispute.model_validate(data)


def _party_of(user: User) -> Party:
    return user.access_role  # customer / worker / council


def create_dispute(user: User, data: DisputeCreate) -> Dispute:
    with connection() as conn:
        booking = conn.execute("SELECT * FROM bookings WHERE id = ?", (data.booking_id,)).fetchone()
        if booking is None:
            raise DisputeError(404, f"Booking {data.booking_id} not found")
        if user.access_role == "customer" and booking["customer_user_id"] != user.id:
            raise DisputeError(403, "You can only raise a dispute on your own booking")
        if user.access_role == "worker":
            assigned = conn.execute(
                "SELECT 1 FROM assignments WHERE booking_id = ? AND worker_id = ?", (data.booking_id, user.worker_id or -1)
            ).fetchone()
            if assigned is None:
                raise DisputeError(403, "You can only raise a dispute on a booking assigned to you")
        already = conn.execute(
            "SELECT id FROM disputes WHERE booking_id = ? AND status = 'open'", (data.booking_id,)
        ).fetchone()
        if already is not None:
            raise DisputeError(409, f"Booking {data.booking_id} already has an open dispute (#{already['id']})")
        paise = int(round(data.amount_rupees * 100)) if data.amount_rupees is not None else None
        cursor = conn.execute(
            "INSERT INTO disputes (booking_id, kind, raised_by, raised_by_user_id, amount_paise, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (data.booking_id, data.kind, _party_of(user), user.id, paise, (data.description or "").strip() or None),
        )
        return _model(conn.execute(_SELECT + " WHERE d.id = ?", (cursor.lastrowid,)).fetchone())


def list_disputes(status: str | None = None, limit: int = 100) -> list[Dispute]:
    with connection() as conn:
        if status:
            rows = conn.execute(_SELECT + " WHERE d.status = ? ORDER BY d.created_at DESC, d.id DESC LIMIT ?", (status, limit))
        else:
            rows = conn.execute(_SELECT + " ORDER BY (d.status = 'open') DESC, d.created_at DESC, d.id DESC LIMIT ?", (limit,))
        return [_model(row) for row in rows]


def resolve_dispute(dispute_id: int, data: DisputeResolve) -> Dispute:
    with connection() as conn:
        row = conn.execute("SELECT status FROM disputes WHERE id = ?", (dispute_id,)).fetchone()
        if row is None:
            raise DisputeError(404, f"Dispute {dispute_id} not found")
        if row["status"] == "resolved":
            raise DisputeError(409, f"Dispute {dispute_id} is already resolved")
        conn.execute(
            "UPDATE disputes SET status = 'resolved', resolution = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (data.resolution.strip(), dispute_id),
        )
        return _model(conn.execute(_SELECT + " WHERE d.id = ?", (dispute_id,)).fetchone())


def dispute_stats(conn: sqlite3.Connection) -> DisputeStats:
    counts = {r["status"]: r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM disputes GROUP BY status")}
    open_, resolved = counts.get("open", 0), counts.get("resolved", 0)
    total = open_ + resolved
    return DisputeStats(open=open_, resolved=resolved, resolution_rate=round(resolved / total, 3) if total else None)
