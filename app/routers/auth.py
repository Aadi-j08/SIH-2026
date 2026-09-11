"""
/auth — sign up, sign in, who am I, sign out.

The session rides in an httpOnly cookie, so the web app never handles the
token itself; API clients get the same token back as `session_token` and
may send it as `Authorization: Bearer ...`. Role checks for other routers
live in app/auth.py (`require_customer`, `require_worker`, `require_council`).
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Header, Response
from pydantic import BaseModel

from app import auth
from app.auth import LoginRequest, SignupRequest, User, current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatus(BaseModel):
    user: User | None
    access_role: auth.Role | None = None
    session_token: str | None = None   # only on sign-up / sign-in, for API clients


def _start_session(response: Response, user: User) -> AuthStatus:
    token = auth.create_session(user.id)
    response.set_cookie(
        auth.SESSION_COOKIE, token,
        max_age=auth.session_days() * 24 * 3600, httponly=True, samesite="lax", path="/",
    )
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
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return AuthStatus(user=None)
