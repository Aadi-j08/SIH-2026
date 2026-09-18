"""Deterministic language identification for assistant transcripts."""
from __future__ import annotations

import re

from app.services.voice import ENGLISH_WORDS, HINDI_WORDS

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
TOKENS = re.compile(r"[a-z\u0900-\u097F]+")
ENGLISH_HINTS = {"a", "an", "the", "check", "booking", "status", "where", "is", "my", "please", "need"}


def detect_language(text: str) -> str:
    """Return en, hi, or hi-Latn (Hinglish); unknown text returns unknown."""
    if DEVANAGARI.search(text):
        return "hi"
    tokens = set(TOKENS.findall(text.lower()))
    hindi = bool(tokens & HINDI_WORDS)
    english = bool(tokens & (ENGLISH_WORDS | ENGLISH_HINTS))
    if hindi:
        return "hi-Latn"
    if english:
        return "en"
    return "unknown"


def supported_languages() -> list[dict[str, str]]:
    return [
        {"code": "en", "name": "English"},
        {"code": "hi", "name": "Hindi"},
        {"code": "hi-Latn", "name": "Hinglish"},
    ]
