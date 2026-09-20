"""
AI Dispute Resolution Advisor & Sentiment Analysis Service for SahakarSetu.

Provides:
1. Automated compromise pricing & diplomatic dispute mediation proposals (Gemini 1.5 Flash with fallback).
2. Review sentiment analysis & grievance toxicity scoring (TextBlob with lexicon fallback).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("sahakarsetu.services.dispute_advisor")

# Optional TextBlob acceleration
HAS_TEXTBLOB = False
try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    log.info("TextBlob not installed; using embedded lexicon-based sentiment analyzer.")

NEGATIVE_WORDS: set[str] = {
    "bad", "terrible", "worst", "fraud", "cheat", "loot", "rude", "late", "broken",
    "ganda", "kharab", "bekar", "chor", "dhokha", "gussa", "delay", "poor", "unprofessional", "expensive",
}
POSITIVE_WORDS: set[str] = {
    "good", "great", "excellent", "best", "polite", "quick", "clean", "perfect",
    "accha", "badhiya", "badiya", "shandar", "sahi", "fast", "helpful", "honest",
}


def analyze_sentiment(text: str) -> dict[str, Any]:
    """
    Evaluates customer or worker review sentiment.
    Returns polarity (-1.0 to +1.0), subjectivity (0.0 to 1.0), and alert flag.
    """
    if not text or not text.strip():
        return {"polarity": 0.0, "label": "neutral", "requires_council_review": False, "score": 0.0}

    if HAS_TEXTBLOB:
        try:
            blob = TextBlob(text)
            polarity = float(round(blob.sentiment.polarity, 2))
            subjectivity = float(round(blob.sentiment.subjectivity, 2))
        except Exception:
            polarity = 0.0
            subjectivity = 0.5
    else:
        # Heuristic word match fallback
        tokens = text.lower().split()
        pos_count = sum(1 for w in tokens if w in POSITIVE_WORDS)
        neg_count = sum(1 for w in tokens if w in NEGATIVE_WORDS)
        total = pos_count + neg_count
        if total == 0:
            polarity = 0.0
        else:
            polarity = round((pos_count - neg_count) / total, 2)
        subjectivity = 0.5

    if polarity > 0.15:
        label = "positive"
    elif polarity < -0.15:
        label = "negative"
    else:
        label = "neutral"

    return {
        "text": text,
        "polarity": polarity,
        "label": label,
        "requires_council_review": polarity < -0.25,
        "engine": "TextBlob" if HAS_TEXTBLOB else "LexiconHeuristic",
    }


def calculate_fair_settlement(
    proposed_rupees: float | None,
    counter_rupees: float | None,
    standard_rupees: float | None = None,
    materials_rupees: float | None = 0.0,
) -> dict[str, Any]:
    """
    Calculates fair mathematical compromise between worker's ask and customer's counter.
    Guarantees material cost coverage first, then splits the remaining labor variance.
    """
    mat = float(materials_rupees or 0.0)
    std = float(standard_rupees or 400.0)
    p = float(proposed_rupees or std)
    c = float(counter_rupees or (p * 0.8))

    # Split labor difference
    labor_proposed = max(0.0, p - mat)
    labor_counter = max(0.0, c - mat)
    labor_compromise = round((labor_proposed + labor_counter) / 2.0, 2)
    
    suggested_total = round(mat + labor_compromise, 2)

    return {
        "worker_proposed_inr": p,
        "customer_counter_inr": c,
        "materials_cost_inr": mat,
        "suggested_settlement_inr": suggested_total,
        "worker_concession_inr": round(p - suggested_total, 2),
        "customer_concession_inr": round(suggested_total - c, 2),
    }


def generate_ai_dispute_recommendation(dispute_data: dict[str, Any]) -> dict[str, Any]:
    """
    Generates neutral, diplomatic settlement recommendation for Sabha council.
    Uses Gemini 1.5 Flash if available, with structured fallback.
    """
    settlement = calculate_fair_settlement(
        proposed_rupees=dispute_data.get("settlement_proposed_rupees"),
        counter_rupees=dispute_data.get("settlement_counter_rupees"),
        standard_rupees=dispute_data.get("settlement_standard_rupees"),
    )

    suggested_inr = settlement["suggested_settlement_inr"]
    kind = dispute_data.get("kind", "payment")
    desc = dispute_data.get("description", "No description provided.")
    worker = dispute_data.get("worker_name", "Worker")
    customer = dispute_data.get("customer_name", "Customer")

    # Fallback template
    fallback_note = (
        f"Recommended Settlement: ₹{suggested_inr:.0f}. "
        f"Split the difference between worker's ask (₹{settlement['worker_proposed_inr']:.0f}) "
        f"and customer's counter (₹{settlement['customer_counter_inr']:.0f}). "
        f"Fair cooperative compromise maintaining member goodwill."
    )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "settlement_breakdown": settlement,
            "recommended_resolution_note": fallback_note,
            "recommended_resolution_hindi": f"सुझाया गया समझौता: ₹{suggested_inr:.0f}। दोनों पक्षों के बीच निष्पक्ष सहमति।",
            "source": "heuristic_rule_engine",
        }

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
        prompt = f"""
You are a neutral civic mediator for the SahakarSetu cooperative council.
Review this dispute:
- Type: {kind}
- Worker: {worker} (Asked: ₹{settlement['worker_proposed_inr']})
- Customer: {customer} (Offered: ₹{settlement['customer_counter_inr']})
- Description: "{desc}"
- Recommended Mathematical Midpoint: ₹{suggested_inr}

Provide a polite, diplomatic 2-sentence resolution note in English and Hindi for the council to adopt.

Respond ONLY with valid JSON:
{{
  "english_note": "...",
  "hindi_note": "..."
}}
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }

        try:
            import httpx
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

        candidate_text = result["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(candidate_text)
        return {
            "settlement_breakdown": settlement,
            "recommended_resolution_note": parsed.get("english_note", fallback_note),
            "recommended_resolution_hindi": parsed.get("hindi_note", ""),
            "source": "gemini_1.5_flash",
        }
    except Exception as e:
        log.warning(f"Gemini dispute mediation failed ({e}); using fallback.")
        return {
            "settlement_breakdown": settlement,
            "recommended_resolution_note": fallback_note,
            "recommended_resolution_hindi": f"सुझाया गया समझौता: ₹{suggested_inr:.0f}। दोनों पक्षों के बीच निष्पक्ष सहमति।",
            "source": "fallback_after_error",
        }

