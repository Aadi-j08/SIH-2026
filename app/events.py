"""
Live updates — the room for real time.

Every write that goes through the API (a booking placed, assigned, accepted,
a price proposed or agreed, a dispute raised, a rate changed) is published
on an in-process bus as a small event: what changed and, where the path
says so, which booking or worker. Signed-in clients hold one server-sent
events stream (GET /events/stream) and reload what they show when an event
concerns them; a plain GET /events?after= serves anything that cannot hold
a stream. No data travels in the event itself — the client re-reads through
the same authorised endpoints it always used.

The bus lives in the process, which is exactly right for one uvicorn
worker; swap `_Bus` for Redis pub/sub when there are several.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import itertools
import json
import re
import threading
from collections import deque
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import User, require_user

Topic = Literal["bookings", "settlements", "disputes", "workers", "rates", "cooperative", "allocation"]


class Event(BaseModel):
    seq: int
    at: str
    topic: Topic
    action: str
    booking_id: int | None = None
    worker_id: int | None = None
    dispute_id: int | None = None


class _Bus:
    def __init__(self, keep: int = 500) -> None:
        self._events: deque[Event] = deque(maxlen=keep)
        self._seq = itertools.count(1)
        self._lock = threading.Lock()
        self.latest = 0

    def publish(self, topic: Topic, action: str, **ids: int | None) -> Event:
        with self._lock:
            event = Event(seq=next(self._seq), at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), topic=topic, action=action, **ids)
            self._events.append(event)
            self.latest = event.seq
        return event

    def since(self, after: int) -> list[Event]:
        with self._lock:
            return [e for e in self._events if e.seq > after]


bus = _Bus()

# path → (topic, action); the first match wins. Only successful writes are published.
_ROUTES: list[tuple[re.Pattern[str], Topic, str]] = [
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/settlement/resolve$"), "settlements", "resolved"),
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/settlement/respond$"), "settlements", "replied"),
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/settlement$"), "settlements", "proposed"),
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/assign$"), "bookings", "assigned"),
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/accept$"), "bookings", "accepted"),
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/decline$"), "bookings", "declined"),
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/complete$"), "bookings", "completed"),
    (re.compile(r"^/bookings/(?P<booking_id>\d+)/rating$"), "bookings", "rated"),
    (re.compile(r"^/bookings$"), "bookings", "placed"),
    (re.compile(r"^/allocation/auto$"), "allocation", "auto"),
    (re.compile(r"^/disputes/(?P<dispute_id>\d+)/resolve$"), "disputes", "resolved"),
    (re.compile(r"^/disputes$"), "disputes", "raised"),
    (re.compile(r"^/workers/(?P<worker_id>\d+)/approve$"), "workers", "approved"),
    (re.compile(r"^/workers/(?P<worker_id>\d+)/availability(/\d+)?$"), "workers", "availability"),
    (re.compile(r"^/workers/(?P<worker_id>\d+)$"), "workers", "updated"),
    (re.compile(r"^/workers$"), "workers", "registered"),
    (re.compile(r"^/rates/[^/]+$"), "rates", "updated"),
    (re.compile(r"^/cooperative$"), "cooperative", "updated"),
]


def classify(method: str, path: str) -> tuple[Topic, str, dict[str, int]] | None:
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    for pattern, topic, action in _ROUTES:
        match = pattern.match(path)
        if match:
            return topic, action, {k: int(v) for k, v in match.groupdict().items() if v is not None}
    return None


class PublishChanges(BaseHTTPMiddleware):
    """Publish an event for every successful write, without touching the endpoints themselves."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        if 200 <= response.status_code < 300:
            hit = classify(request.method, request.url.path)
            if hit:
                topic, action, ids = hit
                bus.publish(topic, action, **ids)
        return response


# ── endpoints ────────────────────────────────────────────────────────────

router = APIRouter(tags=["live"])


@router.get("/events", response_model=list[Event])
def poll_events(after: int = Query(default=0, ge=0), _: User = Depends(require_user)) -> list[Event]:
    """Events since `after` (a seq). For clients that cannot hold a stream."""
    return bus.since(after)


@router.get("/events/stream")
async def stream_events(request: Request, after: int = Query(default=0, ge=0), _: User = Depends(require_user)) -> StreamingResponse:
    """Server-sent events: one `data:` line per change, a comment every 20 s to keep the connection alive."""

    async def generate():
        last = after if after else bus.latest
        yield f"retry: 3000\n: connected seq={last}\n\n"
        idle = 0.0
        while True:
            if await request.is_disconnected():
                return
            fresh = bus.since(last)
            if fresh:
                for event in fresh:
                    last = event.seq
                    yield f"id: {event.seq}\ndata: {json.dumps(event.model_dump())}\n\n"
                idle = 0.0
            else:
                idle += 1.0
                if idle >= 20:
                    idle = 0.0
                    yield ": keep-alive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
