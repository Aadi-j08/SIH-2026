"""Assistant language identification."""
from app.services.language import detect_language, supported_languages


def test_supported_languages_are_explicit():
    assert [item["code"] for item in supported_languages()] == ["en", "hi", "hi-Latn"]


def test_english_hindi_and_hinglish():
    assert detect_language("I need a plumber tomorrow") == "en"
    assert detect_language("मुझे कल प्लंबर चाहिए") == "hi"
    assert detect_language("kal plumber chahiye") == "hi-Latn"


def test_unknown_language_is_not_guessed():
    assert detect_language("xyzzy 123") == "unknown"
