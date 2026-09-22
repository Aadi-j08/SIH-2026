"""
/feedback — collect user feedback so the team can iterate.

Open for anyone to submit (no login required), so real users can report
issues or ideas without friction. Council members see a list endpoint.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from app import auth
from app.database import connection

router = APIRouter(prefix="/feedback", tags=["feedback"])


FeedbackType = Literal["bug", "feature", "general"]


class FeedbackCreate(BaseModel):
    type: FeedbackType = "general"
    rating: int | None = Field(default=None, ge=1, le=5)
    message: str = Field(min_length=1, max_length=2000)


class FeedbackOut(BaseModel):
    id: int
    type: str
    rating: int | None
    message: str
    user_name: str | None
    user_phone: str | None
    user_portal: str | None
    resolved: bool
    created_at: str | None


@router.post("/", response_model=FeedbackOut, status_code=201)
def submit_feedback(
    body: FeedbackCreate = Body(...),
    user: auth.User | None = Depends(auth.current_user),
):
    """Submit feedback. Open endpoint — no login required."""
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO feedback (type, rating, message, user_id, user_name, user_phone, user_portal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                body.type,
                body.rating,
                body.message,
                user.id if user else None,
                user.name if user else None,
                user.phone if user else None,
                user.portal if user else None,
            ),
        )
        feedback_id = cur.lastrowid
        row = conn.execute(
            "SELECT id, type, rating, message, user_name, user_phone, user_portal, resolved, created_at "
            "FROM feedback WHERE id = ?",
            (feedback_id,),
        ).fetchone()
        return FeedbackOut(
            id=row["id"],
            type=row["type"],
            rating=row["rating"],
            message=row["message"],
            user_name=row["user_name"],
            user_phone=row["user_phone"],
            user_portal=row["user_portal"],
            resolved=bool(row["resolved"]),
            created_at=row["created_at"],
        )


@router.get("/", response_model=list[FeedbackOut])
def list_feedback(
    type: str | None = None,
    resolved: bool | None = None,
    _user=Depends(auth.require_council),
):
    """List all feedback submissions. Council only."""
    with connection() as conn:
        query = (
            "SELECT id, type, rating, message, user_name, user_phone, user_portal, resolved, created_at "
            "FROM feedback WHERE 1=1"
        )
        params: list = []
        if type:
            query += " AND type = ?"
            params.append(type)
        if resolved is not None:
            query += " AND resolved = ?"
            params.append(1 if resolved else 0)
        query += " ORDER BY created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [
            FeedbackOut(
                id=row["id"],
                type=row["type"],
                rating=row["rating"],
                message=row["message"],
                user_name=row["user_name"],
                user_phone=row["user_phone"],
                user_portal=row["user_portal"],
                resolved=bool(row["resolved"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]
