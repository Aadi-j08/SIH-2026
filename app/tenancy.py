"""
Federated tenancy for SahakarSetu.

The platform was originally built around a single cooperative (id = 1). It now
supports a *federation* of member cooperatives, each a tenant that owns its own
workers, bookings, rate cards, disputes, settlements and ledger rows.

Tenant resolution:
  - A request declares its tenant with `X-Cooperative-Id` (an integer id) or
    `Cooperative-Scope` (an integer id or a cooperative `code`), or the
    `cooperative_id` cookie.
  - An authenticated user always belongs to exactly one cooperative. If they
    name a different one, the request is rejected with 403.
  - Without any of the above, the default cooperative (id = 1) is used, so the
    single-cooperative deployment and all existing tests keep working.

A contextvar holds the resolved tenant for the duration of a request, which the
DB layer reads through `tenant_id()`. Setting it from ASGI middleware / a
FastAPI dependency is safe: FastAPI runs sync endpoints in a threadpool with a
copy of the request context.
"""
from __future__ import annotations

import contextvars
import logging
from collections.abc import Iterator
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, Request

log = logging.getLogger("sahakarsetu.tenancy")

DEFAULT_COOPERATIVE_ID = 1

# The cooperative a request is operating in (resolved once per request).
_tenant_ctx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("tenant_cooperative_id", default=None)
# The cooperative a request *asked for* before authentication, so auth can
# validate it against the user. None means "not specified" (defaults to 1).
_requested_ctx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("tenant_requested_id", default=None)


def set_tenant_id(cooperative_id: int) -> contextvars.Token:
    """Set the active tenant for this request. Returns a token for `reset_tenant_id`."""
    token = _tenant_ctx.set(cooperative_id)
    _requested_ctx.set(cooperative_id)
    return token


def reset_tenant_id(token: contextvars.Token) -> None:
    _tenant_ctx.reset(token)


def tenant_id() -> int:
    """The cooperative id the current request is operating in, defaulting to 1."""
    return _tenant_ctx.get() or DEFAULT_COOPERATIVE_ID


def requested_cooperative_id() -> Optional[int]:
    """The cooperative id the caller asked for (before auth), if any."""
    return _requested_ctx.get()


def _load_cooperative_by_code(code: str) -> Optional[int]:
    from app.database import connection

    with connection() as conn:
        row = conn.execute("SELECT id FROM cooperative_federations WHERE code = ?", (code,)).fetchone()
    return int(row["id"]) if row else None


def resolve_cooperative_id(raw: Optional[str]) -> Optional[int]:
    """Resolve a header/cookie value to a cooperative id. Accepts an integer id
    or a cooperative code."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    code = raw.upper()
    return _load_cooperative_by_code(code)


def read_requested_cooperative(request: Request) -> Optional[int]:
    """Read the tenant a request is asking for, from headers or the cookie."""
    for value in (request.headers.get("X-Cooperative-Id"), request.headers.get("Cooperative-Scope")):
        if value:
            resolved = resolve_cooperative_id(value)
            if resolved is None:
                log.warning("requested unknown cooperative %r", value)
            return resolved
    cookie = request.cookies.get("cooperative_id")
    return resolve_cooperative_id(cookie)


def resolve_tenant(request: Request) -> Iterator[int]:
    """App-wide FastAPI dependency: set the per-request tenant from the
    request's headers/cookie and yield its id. Every endpoint should depend on
    this (declared once at the app level) so the DB layer always has a tenant.
    """
    requested = read_requested_cooperative(request)
    coop_id = requested if requested is not None else DEFAULT_COOPERATIVE_ID
    token = _tenant_ctx.set(coop_id)
    _requested_ctx.set(requested)
    try:
        yield coop_id
    finally:
        _tenant_ctx.reset(token)


def current_cooperative(user: Optional["object"] = None, request: Optional[Request] = None) -> int:
    """Resolve the tenant for an authenticated request, validating that the user
    agrees with the requested cooperative. Returns the tenant id to operate in.

    Pass the signed-in `User` (or None when anonymous) and the request. Council,
    worker and customer accounts are pinned to their own cooperative, so a
    mismatch between the session's cooperative and the requested one is a 403.
    """
    requested = (read_requested_cooperative(request) if request is not None else requested_cooperative_id()) or DEFAULT_COOPERATIVE_ID
    if user is not None:
        user_coop = getattr(user, "cooperative_id", None)
        if user_coop is not None and user_coop != requested:
            raise HTTPException(
                status_code=403,
                detail=f"This account belongs to cooperative #{user_coop}, not #{requested}.",
            )
    return requested
