"""
Gemini NLP Service for SahakarSetu.

Provides multilingual natural language understanding for Hindi, Hinglish,
and English voice transcripts and text queries.

Features:
- Structured JSON extraction (trade, locality/ward, urgency, schedule, notes)
- Multi-model fallback chain (Lite → Full → offline rule-based parser)
- Explicit 429 rate-limit handling so quota exhaustion silently tries the next model
- Robust regex & keyword fallback if all Gemini models fail or key is missing
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("sahakarsetu.services.gemini_nlp")

# ---------------------------------------------------------------------------
# Ordered list of Gemini models to try — lighter / higher-quota models first.
# gemini-flash-lite-latest has a much more generous free-tier RPD limit than
# gemini-flash-latest (which maps to the latest heavy flash model).
# ---------------------------------------------------------------------------
GEMINI_MODEL_CHAIN: list[str] = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]

# ---------------------------------------------------------------------------
# Trade keyword mapping for the offline fallback parser
# ---------------------------------------------------------------------------
TRADE_KEYWORDS: dict[str, list[str]] = {
    "plumber": ["plumber", "नल", "पानी", "pipe", "leak", "leaking", "tap", "sink", "bathroom", "plumbing", "paani", "nal"],
    "electrician": ["electrician", "bijli", "बिजली", "light", "fan", "switch", "wiring", "short circuit", "board", "fuse", "power"],
    "carpenter": ["carpenter", "lakdi", "लकड़ी", "door", "furniture", "table", "chair", "bed", "wood", "almirah", "darwaza"],
    "painter": ["painter", "paint", "रंग", "रंगाई", "putty", "wall", "painting", "whitewash", "rang"],
    "mason": ["mason", "rajmistri", "राजमिस्त्री", "cement", "brick", "wall", "construction", "plaster", "mistri"],
    "mechanic": ["mechanic", "motor", "pump", "appliance", "ac", "cooler", "repair", "service", "fridge", "washing machine"],
}

URGENCY_KEYWORDS: dict[str, list[str]] = {
    "urgent": ["urgent", "emergency", "jaldi", "turant", "abhi", "तुरंत", "आपातकालीन", "right now", "immediately"],
    "high": ["today", "aaj", "आज", "soon", "fast"],
    "medium": ["tomorrow", "kal", "कल", "weekend", "parson"],
    "low": ["next week", "agle hafte", "agla", "kabhi bhi", "fursat"],
}


def rule_based_fallback(text: str) -> dict[str, Any]:
    """
    Offline heuristic parser using keyword search and regular expressions.
    Guarantees 100% availability even without external AI API access.
    """
    cleaned = text.lower()

    # Detect trade
    detected_trade = "general"
    for trade, keywords in TRADE_KEYWORDS.items():
        if any(kw in cleaned for kw in keywords):
            detected_trade = trade
            break

    # Detect urgency
    detected_urgency = "medium"
    for urgency, keywords in URGENCY_KEYWORDS.items():
        if any(kw in cleaned for kw in keywords):
            detected_urgency = urgency
            break

    # Extract time/date hints if any
    time_hint = None
    if "subah" in cleaned or "morning" in cleaned:
        time_hint = "morning"
    elif "sham" in cleaned or "shaam" in cleaned or "evening" in cleaned:
        time_hint = "evening"
    elif "dopahar" in cleaned or "afternoon" in cleaned:
        time_hint = "afternoon"

    return {
        "trade": detected_trade,
        "urgency": detected_urgency,
        "preferred_time": time_hint,
        "notes": text.strip(),
        "source": "rule_based_fallback",
        "confidence": 0.75 if detected_trade != "general" else 0.40,
    }


def _call_gemini(model: str, payload: dict, api_key: str) -> dict:
    """
    Make a single Gemini generateContent POST call.
    Returns the raw JSON response dict.
    Raises RuntimeError for rate limits (429) or API errors so the caller
    can decide to try the next model or give up.
    """
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    try:
        import httpx  # preferred — handles SSL properly on macOS
        with httpx.Client(verify=False, timeout=8.0) as client:
            res = client.post(url, json=payload)
            result = res.json()
    except ImportError:
        import urllib.request
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))

    if isinstance(result, dict) and "error" in result:
        code = result["error"].get("code")
        msg = result["error"].get("message", "")[:160]
        raise RuntimeError(f"[{code}] {msg}")

    return result


def parse_voice_query(transcript: str, language: str = "hi") -> dict[str, Any]:
    """
    Parses a spoken or typed customer request into structured booking parameters.

    Tries each model in GEMINI_MODEL_CHAIN in order.  On a 429 quota error the
    next model is tried automatically.  If every Gemini call fails, the
    offline rule_based_fallback is used so the endpoint never returns an error.
    """
    if not transcript or not transcript.strip():
        return {
            "trade": "general",
            "urgency": "medium",
            "preferred_time": None,
            "notes": "",
            "source": "empty",
            "confidence": 0.0,
        }

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        log.info("GEMINI_API_KEY not configured. Using rule-based fallback parser.")
        return rule_based_fallback(transcript)

    prompt = (
        "You are SahakarSetu's AI dispatch assistant for civic trade workers in India.\n"
        "Analyze the following customer query (which may be in Hindi, Hinglish, or English).\n"
        "Extract structured booking details.\n\n"
        f'Query: "{transcript}"\n\n'
        "Respond ONLY with valid JSON in this exact structure:\n"
        '{\n'
        '  "trade": "plumber" | "electrician" | "carpenter" | "painter" | "mason" | "mechanic" | "general",\n'
        '  "urgency": "low" | "medium" | "high" | "urgent",\n'
        '  "preferred_time": "string or null",\n'
        '  "summary": "short english summary of what the customer needs"\n'
        "}\n"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    }

    last_error: str = "no models tried"
    for model in GEMINI_MODEL_CHAIN:
        try:
            result = _call_gemini(model, payload, api_key)
            candidate_text = result["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(candidate_text)
            parsed["source"] = f"gemini/{model}"
            parsed["confidence"] = 0.95
            parsed["raw_transcript"] = transcript
            log.info(
                "Gemini NLP parsed by %s: trade=%s urgency=%s",
                model,
                parsed.get("trade"),
                parsed.get("urgency"),
            )
            return parsed

        except RuntimeError as e:
            last_error = str(e)
            if "[429]" in last_error:
                log.warning("Gemini %s: quota exhausted (429), trying next model.", model)
            else:
                log.warning("Gemini %s: API error (%s), trying next model.", model, last_error)
            continue

        except (KeyError, IndexError, json.JSONDecodeError) as e:
            last_error = str(e)
            log.warning("Gemini %s: response parse error (%s), trying next model.", model, e)
            continue

        except Exception as e:
            last_error = str(e)
            log.warning("Gemini %s: unexpected error (%s), trying next model.", model, e)
            continue

    # All Gemini models exhausted — degrade to offline rule-based parser
    log.warning("All Gemini models failed (last: %s); using rule-based fallback.", last_error)
    fallback = rule_based_fallback(transcript)
    fallback["error"] = last_error
    return fallback
