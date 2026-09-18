"""Explainable intent and entity extraction for the voice assistant."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.services.language import detect_language
from app.services.voice import parse_availability
from app.trades import CANONICAL_TRADES, TRADE_ALIASES, canonical_trade

INTENTS = (
    "create_booking", "check_booking_status", "set_availability", "check_worker_jobs",
    "accept_job", "decline_job", "check_worker_earnings", "get_forecast",
    "get_staffing_shortage", "explain_assignment", "request_reassignment",
)

_INTENT_WORDS: dict[str, tuple[str, ...]] = {
    "set_availability": ("available", "free", "khali", "खाली", "busy", "nahi", "availability"),
    "create_booking": ("book", "booking", "need", "chahiye", "चाहिए", "service", "kaam karwana"),
    "check_booking_status": ("status", "where", "kahan", "कहाँ", "booking", "track"),
    "check_worker_jobs": ("jobs", "job", "kaam", "काम", "assignments"),
    "accept_job": ("accept", "haan", "हाँ", "le lunga", "take job"),
    "decline_job": ("decline", "reject", "pass", "mana", "मना", "unwell", "too far"),
    "request_reassignment": ("reassign", "reassignment", "pass", "another worker", "dusra"),
    "check_worker_earnings": ("earnings", "earned", "kamai", "कमाई", "payout", "money"),
    "get_forecast": ("forecast", "demand", "expected", "aane wale"),
    "get_staffing_shortage": ("shortage", "staffing", "enough workers", "kami", "कमी"),
    "explain_assignment": ("why assigned", "why me", "explain assignment", "kyun mujhe", "क्यों"),
}


def _booking_id(text: str) -> int | None:
    match = re.search(r"\b(?:booking|job|assignment)?\s*#?\s*(\d+)\b", text.lower())
    return int(match.group(1)) if match else None


def _trade(text: str) -> str | None:
    lower = text.lower()
    for alias in sorted(TRADE_ALIASES, key=len, reverse=True):
        if alias in lower:
            return TRADE_ALIASES[alias]
    return None


def _location(text: str) -> str | None:
    matches = list(re.finditer(r"\b(?:in|near|around|mein|par|पास|में)\s+([\w][\w -]{1,80})", text, re.IGNORECASE))
    match = matches[-1] if matches else None
    if match is None:
        match = re.search(r"\bat\s+([A-Za-z][\w -]{1,80})", text, re.IGNORECASE)
    if not match:
        return None
    value = re.split(r"\b(?:tomorrow|today|kal|aaj|on|for|at|from|se|to|and|aur)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
    value = value.strip(" ,.!?")
    return value or None


def _date_entity(text: str) -> str | None:
    lower = text.lower()
    if re.search(r"\b(tomorrow|tmrw|kal|कल)\b", lower):
        return "tomorrow"
    if re.search(r"\b(today|aaj|आज)\b", lower):
        return "today"
    return None


def _time_entity(text: str) -> tuple[str | None, str | None]:
    if not re.search(r"\b\d{1,2}(?::\d{2})?\b|\b(?:morning|afternoon|evening|night|subah|dopahar|shaam|raat)\b", text.lower()):
        return None, None
    parsed = parse_availability(text)
    if not parsed.windows:
        return None, None
    window = parsed.windows[0]
    return window.start, window.end if re.search(r"\b(?:to|se|tak|till|until|and|aur|-)\b", text.lower()) else None


def _score(text: str, intent: str, entities: dict[str, Any]) -> float:
    tokens = re.findall(r"[a-z\u0900-\u097F]+", text.lower())
    matched = sum(1 for word in _INTENT_WORDS[intent] if word in text.lower())
    confidence = 0.55 + min(0.25, matched * 0.08)
    if intent in {"create_booking", "set_availability"}:
        confidence += 0.12 if entities.get("trade") or intent == "set_availability" else 0
        confidence += 0.08 if entities.get("start_time") else 0
        confidence += 0.05 if entities.get("date") else 0
        confidence += 0.03 if entities.get("location") else 0
        confidence += 0.03 if entities.get("end_time") else 0
    elif intent in {"check_booking_status", "accept_job", "decline_job", "explain_assignment"}:
        confidence += 0.18 if entities.get("booking_id") is not None else -0.20
    if len(tokens) < 2:
        confidence -= 0.2
    return round(max(0.0, min(0.99, confidence)), 2)


def parse_intent(transcript: str, reference_date: date | None = None) -> dict[str, Any]:
    """Classify a transcript and extract only explicitly spoken entities."""
    text = transcript.strip()
    lower = text.lower()
    availability = parse_availability(text, reference_date) if text else None
    entities: dict[str, Any] = {}
    trade = _trade(text)
    booking_id = _booking_id(text)
    if trade:
        entities["trade"] = trade
    if booking_id is not None:
        entities["booking_id"] = booking_id
    if _date_entity(text):
        entities["date"] = _date_entity(text)
    start, end = _time_entity(text)
    if start:
        entities["start_time"] = start
    if end:
        entities["end_time"] = end
    location = _location(text)
    if location and ("create" in lower or "book" in lower or "service" in lower):
        entities["location"] = location
    scores = {
        intent: sum(1 for word in words if word in lower)
        for intent, words in _INTENT_WORDS.items()
    }
    intent = max(scores, key=scores.get) if text and max(scores.values(), default=0) else "unknown"
    if intent == "set_availability" and availability and not availability.windows:
        intent = "unknown"
    if intent == "create_booking" and "booking" in lower and any(word in lower for word in ("status", "where", "track")):
        intent = "check_booking_status"
    if intent == "decline_job" and any(word in lower for word in ("reassign", "another worker", "dusra")):
        intent = "request_reassignment"
    confidence = _score(text, intent, entities) if intent != "unknown" else 0.25
    if intent == "create_booking" and not entities.get("trade"):
        confidence = min(confidence, 0.84)
    if intent == "unknown":
        entities = {}
    return {"language": detect_language(text), "intent": intent, "entities": entities, "confidence": confidence}
