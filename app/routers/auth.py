"""
/auth — sign up, sign in, who am I, sign out.

The session rides in an httpOnly cookie, so the web app never handles the
token itself. `require_portal(...)` is the dependency other routers can use
to insist on a signed-in user of a particular portal.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel

from app import auth
from app.auth import LoginRequest, SignupRequest, User

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatus(BaseModel):
    user: User | None


def current_user(session: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE)) -> User | None:
    return auth.user_for_token(session)


def require_portal(portal: Literal["ghar", "kaam", "sabha"]):
    """Dependency factory: `Depends(require_portal("sabha"))` → the signed-in Sabha user, else 401/403."""

    def dependency(user: User | None = Depends(current_user)) -> User:
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in first")
        if user.portal != portal:
            raise HTTPException(status_code=403, detail=f"This is a {portal.capitalize()} area; you are signed in to {user.portal.capitalize()}")
        return user

    return dependency


def _start_session(response: Response, user: User) -> AuthStatus:
    token = auth.create_session(user.id)
    response.set_cookie(
        auth.SESSION_COOKIE, token,
        max_age=auth.session_days() * 24 * 3600, httponly=True, samesite="lax", path="/",
    )
    return AuthStatus(user=user)


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
    return AuthStatus(user=user)


@router.post("/logout", response_model=AuthStatus)
def logout(response: Response, session: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE)):
    auth.end_session(session)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return AuthStatus(user=None)
