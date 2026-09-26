"""
Accounts, sessions and roles, one set per portal.

Ghar (households) and Kaam (workers) sign up freely; Sabha (the council)
needs the cooperative's council code. A Kaam sign-up also creates the
worker record the allocation engine uses. Sessions are random tokens kept
in the sessions table (hashed) and handed to the browser as an httpOnly
cookie — no external auth provider, by design. API clients (Swagger, curl,
tests) may send the same token as `Authorization: Bearer <token>`; sign-up
and sign-in responses include it as `session_token` for that purpose.

Roles follow the portal an account belongs to:

    ghar  -> customer    books, reads and rates their own bookings
    kaam  -> worker      manages their own availability, completes their own jobs
    sabha -> council     runs the cooperative: assigns work, sees everything

The FastAPI dependencies at the bottom (`require_role`, `require_customer`,
...) are what the endpoints use to identify the caller; the frontend's
route choice is never trusted on its own.

Config (environment):
    SAHAKARSETU_COUNCIL_CODE   code(s) that unlock Sabha sign-up, comma-separated (default SABHA-2026)
    SAHAKARSETU_SESSION_DAYS   session lifetime in days (default 30)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from typing import Literal

from fastapi import Cookie, Depends, Header, HTTPException
from pydantic import BaseModel, Field, computed_field, model_validator

from app import tenancy
from app.database import connection
from app.schemas import WorkerCreate

Portal = Literal["ghar", "kaam", "sabha"]
PORTALS: tuple[Portal, ...] = ("ghar", "kaam", "sabha")

Role = Literal["customer", "worker", "council"]
ROLES: tuple[Role, ...] = ("customer", "worker", "council")
ROLE_OF_PORTAL: dict[str, Role] = {"ghar": "customer", "kaam": "worker", "sabha": "council"}
PORTAL_OF_ROLE: dict[str, Portal] = {role: portal for portal, role in ROLE_OF_PORTAL.items()}

SESSION_COOKIE = "sahakarsetu_session"
PBKDF2_ITERATIONS = 200_000

# Where the cooperative operates; a Kaam sign-up without GPS lands here.
DEFAULT_LATITUDE, DEFAULT_LONGITUDE = 23.18, 77.42


def council_codes() -> list[str]:
    """Accepted council codes, upper-cased. Several may be set, e.g. one per council member: "SABHA-2026,SETU-7731"."""
    raw = os.environ.get("SAHAKARSETU_COUNCIL_CODE", "SABHA-2026")
    return [code.strip().upper() for code in raw.split(",") if code.strip()]


def council_code() -> str:
    """The primary council code (kept for callers that expect one)."""
    return council_codes()[0]


def is_council_code(candidate: str | None) -> bool:
    given = (candidate or "").strip().upper()
    return any(hmac.compare_digest(given, code) for code in council_codes())


def session_days() -> int:
    return int(os.environ.get("SAHAKARSETU_SESSION_DAYS", "30"))


# ── models ───────────────────────────────────────────────────────────────

class User(BaseModel):
    """What the browser sees of an account. Never includes the password hash."""
    id: int
    portal: Portal
    name: str
    phone: str
    locality: str | None = None
    role: str | None = None
    worker_id: int | None = None
    languages: list[str] = Field(default_factory=list)
    created_at: str | None = None
    cooperative_id: int = 1
    worker_status: str | None = None
    """Kaam workers: 'pending' until council approves, then 'active'.
    None for non-worker accounts."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def access_role(self) -> Role:
        """customer / worker / council — what the account may do (`role` is a council member's title)."""
        return ROLE_OF_PORTAL[self.portal]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_council(self) -> bool:
        return self.portal == "sabha"

    @property
    def is_council(self) -> bool:
        return self.portal == "sabha"


class SignupRequest(BaseModel):
    portal: Portal
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=10, max_length=20, description="Indian mobile number; spaces, dashes and +91 are stripped")
    password: str = Field(min_length=6, max_length=200)
    locality: str | None = Field(default=None, max_length=120, description="Ghar and Kaam: the area the person lives / works in")
    # Kaam
    trade: str | None = Field(default=None, max_length=50)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    languages: list[str] = Field(default_factory=list, max_length=10)
    # Sabha
    role: str | None = Field(default=None, max_length=60)
    council_code: str | None = Field(default=None, max_length=60)
    cooperative_code: str | None = Field(default=None, max_length=60, description="Member cooperative to join; defaults to the current tenant")

    @model_validator(mode="after")
    def _portal_specific_fields(self) -> "SignupRequest":
        if self.portal == "kaam" and not (self.trade or "").strip():
            raise ValueError("Kaam sign-up needs a trade")
        if self.portal == "sabha":
            if not (self.council_code or "").strip():
                raise ValueError("Sabha sign-up needs the council code")
            self.role = (self.role or "member").strip()
        return self


class LoginRequest(BaseModel):
    portal: Portal
    phone: str = Field(min_length=10, max_length=20)
    password: str = Field(min_length=1, max_length=200)


# ── helpers ──────────────────────────────────────────────────────────────

class AuthError(Exception):
    """A sign-up or sign-in problem the user can act on; the router maps it to an HTTP status."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def normalise_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) != 10:
        raise AuthError(422, "Enter a 10-digit mobile number")
    return digits


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), expected)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _user(row: sqlite3.Row) -> User:
    data = dict(row)
    data.pop("password_hash", None)
    data["languages"] = json.loads(data.get("languages") or "[]")
    worker_status = None
    wid = data.get("worker_id")
    if wid:
        from app.database import connection
        with connection() as conn:
            st = conn.execute("SELECT status FROM workers WHERE id = ?", (wid,)).fetchone()
            if st:
                worker_status = st[0]
    data["worker_status"] = worker_status
    return User.model_validate(data)


# ── accounts ─────────────────────────────────────────────────────────────

def signup(data: SignupRequest) -> User:
    phone = normalise_phone(data.phone)
    if data.portal == "sabha" and not is_council_code(data.council_code):
        raise AuthError(403, "That council code is not right. Ask your cooperative's secretary for it.")

    cooperative_id = None
    if data.cooperative_code:
        from app.cooperative import get_cooperative_by_code

        coop = get_cooperative_by_code(data.cooperative_code)
        if coop is None:
            raise AuthError(404, f"There is no cooperative with code {data.cooperative_code}")
        cooperative_id = coop.id
    if cooperative_id is None:
        cooperative_id = tenancy.tenant_id()

    worker_id: int | None = None
    with connection() as conn:
        if data.portal == "kaam":
            from app.repository import _normalise_trade, _dump_windows
            cursor = conn.execute(
                "INSERT INTO workers (name, phone, trade, latitude, longitude, rating, availability, status, cooperative_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data.name.strip(), phone, _normalise_trade((data.trade or "").strip()),
                 data.latitude if data.latitude is not None else DEFAULT_LATITUDE,
                 data.longitude if data.longitude is not None else DEFAULT_LONGITUDE,
                 None, "[]", "pending", cooperative_id),
            )
            worker_id = cursor.lastrowid

        try:
            cursor = conn.execute(
                "INSERT INTO users (portal, phone, name, password_hash, locality, role, worker_id, languages, cooperative_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data.portal, phone, data.name.strip(), hash_password(data.password),
                 (data.locality or None) and data.locality.strip(), data.role, worker_id,
                 json.dumps([lang.strip() for lang in data.languages if lang.strip()]), cooperative_id),
            )
        except sqlite3.IntegrityError as exc:
            raise AuthError(409, f"There is already a {data.portal.capitalize()} account for this number. Sign in instead.") from exc
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _user(row)


def login(data: LoginRequest) -> User:
    phone = normalise_phone(data.phone)
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE portal = ? AND phone = ?", (data.portal, phone)).fetchone()
    if row is None or not verify_password(data.password, row["password_hash"]):
        raise AuthError(401, "Wrong mobile number or password for this portal.")
    return _user(row)


def get_user(user_id: int) -> User | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user(row) if row else None


# ── sessions ─────────────────────────────────────────────────────────────

def create_session(user_id: int) -> str:
    """Start a session and return the raw token for the cookie (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=session_days())).isoformat()
    with connection() as conn:
        conn.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                     (_hash_token(token), user_id, expires))
    return token


def user_for_token(token: str | None) -> User | None:
    if not token:
        return None
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with connection() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?",
            (_hash_token(token), now),
        ).fetchone()
    return _user(row) if row else None


def end_session(token: str | None) -> None:
    if not token:
        return
    with connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))


# ── who is calling? (FastAPI dependencies) ───────────────────────────────

def session_token_from(session_cookie: str | None, authorization: str | None) -> str | None:
    """The session token from the cookie, or from `Authorization: Bearer ...` for API clients."""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
    return session_cookie


def current_user(
    session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    authorization: str | None = Header(default=None),
) -> User | None:
    """The signed-in user, or None. Never raises: endpoints decide what anonymity means."""
    return user_for_token(session_token_from(session, authorization))


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in first")
    if user.cooperative_id != tenancy.tenant_id():
        raise HTTPException(
            status_code=403,
            detail=f"This account belongs to cooperative #{user.cooperative_id}, not the requested tenant.",
        )
    return user


def require_role(*roles: Role):
    """Dependency factory: `Depends(require_role("council"))` → the signed-in user if their role is allowed, else 401/403."""
    allowed = set(roles)

    def dependency(user: User = Depends(require_user)) -> User:
        if user.access_role not in allowed:
            wanted = " or ".join(sorted(allowed))
            raise HTTPException(
                status_code=403,
                detail=f"This action is for {wanted} accounts; you are signed in as {user.access_role}",
            )
        return user

    return dependency


# Council members administer the cooperative, so they may do what customers and workers can.
require_customer = require_role("customer", "council")
require_worker = require_role("worker", "council")
require_council = require_role("council")
