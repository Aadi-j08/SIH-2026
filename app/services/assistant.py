"""Voice-first assistant orchestration with deterministic, permission-aware tools."""
from __future__ import annotations

import datetime as dt
import json
from typing import Any

from pydantic import BaseModel, Field

from app import kaam, ownership, repository
from app.auth import User
from app.database import connection
from app.schemas import AvailabilityWindow, BookingCreate
from app.services import booking_flow, forecast, staffing
from app.services.intent import parse_intent
from app.services.voice import parse_availability

WRITE_INTENTS = {"create_booking", "set_availability", "accept_job", "decline_job", "request_reassignment"}


class AssistantMessage(BaseModel):
    transcript: str = Field(min_length=1, max_length=1000)
    confirmed: bool = False
    reference_date: dt.date | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class AssistantResponse(BaseModel):
    transcript: str
    language: str
    intent: str
    entities: dict[str, Any]
    confidence: float
    requires_confirmation: bool
    confirmation_message: str | None
    action_preview: dict[str, Any]
    reply: str
    result: Any | None = None


def _audit(user: User, request: AssistantMessage, parsed: dict[str, Any], outcome: str) -> None:
    with connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS assistant_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            intent TEXT NOT NULL, transcript TEXT NOT NULL, entities TEXT NOT NULL,
            confirmed INTEGER NOT NULL, outcome TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute(
            "INSERT INTO assistant_audit (user_id, intent, transcript, entities, confirmed, outcome) VALUES (?, ?, ?, ?, ?, ?)",
            (user.id, parsed["intent"], request.transcript, json.dumps(parsed["entities"], default=str), int(request.confirmed), outcome),
        )


def _worker_id(user: User) -> int:
    if user.access_role != "worker" or user.worker_id is None:
        raise PermissionError("Only a worker can use this assistant tool")
    return user.worker_id


def _missing(parsed: dict[str, Any]) -> list[str]:
    intent, entities = parsed["intent"], parsed["entities"]
    required: dict[str, tuple[str, ...]] = {
        "create_booking": ("trade", "location", "date", "start_time"),
        "set_availability": ("date", "start_time"),
        "check_booking_status": ("booking_id",), "accept_job": ("booking_id",),
        "decline_job": ("booking_id",), "explain_assignment": ("booking_id",),
        "request_reassignment": ("booking_id",),
        "get_forecast": ("trade",), "get_staffing_shortage": ("trade",),
    }
    return [name for name in required.get(intent, ()) if entities.get(name) is None]


def _confirmation(intent: str, entities: dict[str, Any]) -> str:
    if intent == "set_availability":
        return f"You want to set availability for {entities.get('date', 'the stated day')} from {entities.get('start_time')}" + (f" to {entities['end_time']}" if entities.get("end_time") else "") + ". Save it?"
    if intent == "create_booking":
        return f"Book {entities.get('trade')} at {entities.get('location')} for {entities.get('date')} at {entities.get('start_time')}. Confirm?"
    if intent == "accept_job": return f"Accept booking {entities['booking_id']}?"
    if intent == "decline_job": return f"Decline booking {entities['booking_id']}?"
    if intent == "request_reassignment": return f"Request a different worker for booking {entities['booking_id']}?"
    return "Please confirm this action."


def _preview(intent: str, entities: dict[str, Any]) -> dict[str, Any]:
    return {"type": intent, **{key: value for key, value in entities.items() if key in {"booking_id", "trade", "location", "date", "start_time", "end_time"}}}


def _booking_detail_for(user: User, booking_id: int) -> dict[str, Any]:
    from app.booking_flow_db import booking_flow_connection

    with booking_flow_connection() as conn:
        detail = booking_flow.get_booking_detail(conn, booking_id)
    if user.is_council:
        return detail
    booking = detail["booking"]
    assignment = detail.get("assignment") or {}
    assigned_worker = (assignment.get("worker") or {}).get("id")
    if user.access_role == "customer" and booking.get("customer_user_id") == user.id:
        return detail
    if user.access_role == "worker" and assigned_worker == user.worker_id:
        return detail
    raise PermissionError("You do not have access to this booking")


def _execute(user: User, request: AssistantMessage, intent: str, entities: dict[str, Any]) -> Any:
    if intent == "set_availability":
        worker = repository.get_worker(_worker_id(user))
        if worker is None: raise ValueError("Worker record not found")
        parsed = parse_availability(request.transcript, request.reference_date)
        repository.set_worker_availability(worker.id, parsed.windows, replace=False)
        return "Your availability has been saved."
    if intent == "create_booking":
        if request.latitude is None or request.longitude is None:
            raise ValueError("Your location is needed to place this booking. Use the normal form or provide location access.")
        booking = repository.create_booking(BookingCreate(
            customer_name=user.name, customer_phone=user.phone, trade=entities["trade"],
            latitude=request.latitude, longitude=request.longitude,
            address=entities["location"], scheduled_for=dt.datetime.combine(
                (request.reference_date or dt.date.today()) + dt.timedelta(days=1 if entities["date"] == "tomorrow" else 0),
                dt.time.fromisoformat(entities["start_time"]),
            ),
        ))
        ownership.attach_customer(booking.id, user)
        assignment = None
        try:
            from app.booking_flow_db import booking_flow_connection
            with booking_flow_connection() as conn:
                assignment = booking_flow.assign_booking(conn, booking.id)
        except booking_flow.NoEligibleWorker:
            pass
        assignment_result = None
        if assignment:
            assigned_worker = assignment.get("worker")
            worker_data = assigned_worker.model_dump(mode="json") if hasattr(assigned_worker, "model_dump") else assigned_worker
            assignment_result = {**assignment, "worker": worker_data}
        return {"booking": repository.get_booking(booking.id).model_dump(mode="json"), "assignment": assignment_result}
    booking_id = int(entities["booking_id"])
    if intent == "accept_job":
        kaam.accept(booking_id, _worker_id(user)); return f"Booking {booking_id} accepted."
    if intent == "decline_job":
        return kaam.decline(booking_id, _worker_id(user), kaam.DeclineRequest(reason="other")).model_dump(mode="json")
    if intent == "request_reassignment":
        return kaam.decline(booking_id, _worker_id(user), kaam.DeclineRequest(reason="other")).model_dump(mode="json")
    raise ValueError("This assistant action is not writable")


def handle(user: User, request: AssistantMessage) -> AssistantResponse:
    parsed = parse_intent(request.transcript, request.reference_date)
    intent, entities, confidence = parsed["intent"], parsed["entities"], parsed["confidence"]
    action_preview = _preview(intent, entities)
    if intent == "unknown":
        response = AssistantResponse(transcript=request.transcript, language=parsed["language"], intent=intent, entities={}, confidence=confidence, requires_confirmation=False, confirmation_message=None, action_preview={}, reply="I could not understand that. Please repeat it or use the normal form.")
        _audit(user, request, parsed, "fallback"); return response
    allowed = {
        "customer": {"create_booking", "check_booking_status"},
        "worker": {"set_availability", "check_worker_jobs", "accept_job", "decline_job", "request_reassignment", "check_worker_earnings"},
        "council": {"get_forecast", "get_staffing_shortage", "explain_assignment", "check_booking_status"},
    }
    if intent not in allowed[user.access_role]:
        _audit(user, request, parsed, "permission_denied")
        raise PermissionError("This assistant tool is not available for your role")
    missing = _missing(parsed)
    if confidence < 0.85:
        reply = "Please tell me " + ", ".join(missing).replace("_", " ") + "." if missing else "I am not confident enough to act on that. Please repeat it."
        response = AssistantResponse(transcript=request.transcript, language=parsed["language"], intent=intent, entities=entities, confidence=confidence, requires_confirmation=False, confirmation_message=None, action_preview=action_preview, reply=reply)
        _audit(user, request, parsed, "low_confidence"); return response
    if missing:
        question = "Please tell me " + ", ".join(missing).replace("_", " ") + "."
        response = AssistantResponse(transcript=request.transcript, language=parsed["language"], intent=intent, entities=entities, confidence=confidence, requires_confirmation=False, confirmation_message=None, action_preview=action_preview, reply=question)
        _audit(user, request, parsed, "needs_clarification"); return response
    if intent in WRITE_INTENTS and not request.confirmed:
        message = _confirmation(intent, entities)
        response = AssistantResponse(transcript=request.transcript, language=parsed["language"], intent=intent, entities=entities, confidence=confidence, requires_confirmation=True, confirmation_message=message, action_preview=action_preview, reply="Please confirm this action before I make the change.")
        _audit(user, request, parsed, "awaiting_confirmation"); return response
    try:
        if intent in WRITE_INTENTS:
            result = _execute(user, request, intent, entities)
            _audit(user, request, parsed, "executed")
            reply = result if isinstance(result, str) else "The requested change was completed."
            return AssistantResponse(transcript=request.transcript, language=parsed["language"], intent=intent, entities=entities, confidence=confidence, requires_confirmation=False, confirmation_message=None, action_preview=action_preview, reply=reply, result=None if isinstance(result, str) else result)
        result: Any
        if intent == "check_worker_jobs": result = kaam.jobs(_worker_id(user))
        elif intent == "check_worker_earnings": result = kaam.summary(_worker_id(user)).model_dump(mode="json")
        elif intent == "check_booking_status":
            result = _booking_detail_for(user, int(entities["booking_id"]))
        elif intent == "explain_assignment":
            result = _booking_detail_for(user, int(entities["booking_id"]))
        elif intent == "get_forecast": result = forecast.forecast_demand(repository.demand_dates(entities["trade"]), trade=entities["trade"], horizon_days=7).model_dump(mode="json")
        else:
            workers = repository.worker_profiles(entities["trade"])
            demand = forecast.forecast_demand(repository.demand_dates(entities["trade"]), trade=entities["trade"], horizon_days=7)
            result = staffing.staffing_forecast(demand, workers, trade=entities["trade"]).model_dump(mode="json")
        _audit(user, request, parsed, "read")
        return AssistantResponse(transcript=request.transcript, language=parsed["language"], intent=intent, entities=entities, confidence=confidence, requires_confirmation=False, confirmation_message=None, action_preview={"type": intent, "result": result}, reply="Here is what I found.")
    except (PermissionError, ValueError, kaam.KaamError, booking_flow.BookingFlowError) as exc:
        _audit(user, request, parsed, "failed")
        raise exc
