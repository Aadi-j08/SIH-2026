import datetime

from app.services.bhashini_client import BhashiniClient, SpeechConfig


def test_offline_fallback_returns_parser_summary():
    client = BhashiniClient(SpeechConfig())  # remote disabled
    payload = client.parse(b"", "kal subah free hoon", reference_date=datetime.date(2026, 9, 11))
    assert payload["transcript"] == "kal subah free hoon"
    assert "tomorrow" in payload["summary"]
    assert payload["language"] in ("hi", "mixed")
