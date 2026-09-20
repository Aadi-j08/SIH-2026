"""
/auth — sign up, sign in, who am I, sign out.

The session rides in an httpOnly cookie, so the web app never handles the
token itself; API clients get the same token back as `session_token` and
may send it as `Authorization: Bearer ...`. Role checks for other routers
live in app/auth.py (`require_customer`, `require_worker`, `require_council`).

When the SPA is on another origin (e.g. Cloudflare Pages), set
SAHAKARSETU_COOKIE_SECURE=1 and SAHAKARSETU_COOKIE_SAMESITE=none so the
browser will send the cookie on cross-site API calls. The SPA also keeps
session_token in localStorage and sends it as Bearer (needed when
third-party cookies are blocked).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Header, Response
from pydantic import BaseModel

from app import auth
from app.auth import LoginRequest, SignupRequest, User, current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatus(BaseModel):
    user: User | None
    access_role: auth.Role | None = None
    session_token: str | None = None   # only on sign-up / sign-in, for API clients


def _cookie_kwargs() -> dict:
    """Cookie flags for same-origin (default) or cross-origin Pages → API."""
    samesite = os.environ.get("SAHAKARSETU_COOKIE_SAMESITE", "lax").strip().lower() or "lax"
    if samesite not in ("lax", "strict", "none"):
        samesite = "lax"
    secure_raw = os.environ.get("SAHAKARSETU_COOKIE_SECURE", "").strip().lower()
    secure = secure_raw in ("1", "true", "yes") or samesite == "none"
    return {
        "max_age": auth.session_days() * 24 * 3600,
        "httponly": True,
        "samesite": samesite,
        "secure": secure,
        "path": "/",
    }


def _start_session(response: Response, user: User) -> AuthStatus:
    token = auth.create_session(user.id)
    response.set_cookie(auth.SESSION_COOKIE, token, **_cookie_kwargs())
    return AuthStatus(user=user, access_role=user.access_role, session_token=token)


@router.post("/signup", response_model=AuthStatus, status_code=201)
def signup(body: SignupRequest, response: Response):
    try:
        user = auth.signup(body)
    except auth.AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return _start_session(response, user)


@router.post("/login", response_model=AuthStatus)
def login(body: LoginRequest, response: Response):
    try:
        user = auth.login(body)
    except auth.AuthError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc
    return _start_session(response, user)


@router.get("/me", response_model=AuthStatus)
def me(user: User | None = Depends(current_user)):
    return AuthStatus(user=user, access_role=user.access_role if user else None)


@router.post("/logout", response_model=AuthStatus)
def logout(
    response: Response,
    session: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE),
    authorization: str | None = Header(default=None),
):
    auth.end_session(auth.session_token_from(session, authorization))
    # Mirror the same flags used on set, or the browser keeps the old cookie.
    kwargs = _cookie_kwargs()
    response.delete_cookie(
        auth.SESSION_COOKIE,
        path=kwargs["path"],
        secure=kwargs["secure"],
        samesite=kwargs["samesite"],
    )
    return AuthStatus(user=None)
