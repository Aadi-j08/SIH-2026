"""
Tests for Gemini NLP & Voice Intent Service.
"""
from app.services.gemini_nlp import parse_voice_query, rule_based_fallback


def test_fallback_hindi_plumber_query():
    text = "bhaiyya ghar me nal leak ho raha hai paani beh raha hai jaldi aao"
    result = rule_based_fallback(text)
    assert result["trade"] == "plumber"
    assert result["urgency"] == "urgent"
    assert result["source"] == "rule_based_fallback"
    assert result["confidence"] > 0.5


def test_fallback_hinglish_electrician_query():
    text = "kal subah bijli switch theek karne ke liye electrician chahiye"
    result = rule_based_fallback(text)
    assert result["trade"] == "electrician"
    assert result["urgency"] == "medium"
    assert result["preferred_time"] == "morning"


def test_fallback_carpenter_query():
    text = "darwaza aur table repair karna hai agle hafte"
    result = rule_based_fallback(text)
    assert result["trade"] == "carpenter"
    assert result["urgency"] == "low"


def test_empty_query():
    result = parse_voice_query("")
    assert result["trade"] == "general"
    assert result["confidence"] == 0.0


def test_english_painter_query():
    text = "Need a painter for wall whitewash and painting today"
    result = parse_voice_query(text)
    assert result["trade"] == "painter"
    assert result["urgency"] in ("high", "urgent")
