"""Voice availability parser (Hindi / English / Hinglish transcripts)."""
from __future__ import annotations

from datetime import date

import pytest

from app.schemas import AvailabilityWindow
from app.services.voice import describe_windows, detect_language, parse_availability

TODAY = date(2026, 9, 11)       # Friday
TOMORROW = date(2026, 9, 12)


def windows(text: str) -> list[AvailabilityWindow]:
    return parse_availability(text, TODAY).windows


def test_hinglish_tomorrow_morning():
    assert windows("kal subah free hoon") == [AvailabilityWindow(date=TOMORROW, start="06:00", end="12:00")]


def test_devanagari_tomorrow_morning():
    result = parse_availability("मैं कल सुबह खाली हूँ", TODAY)
    assert result.language == "hi"
    assert result.windows == [AvailabilityWindow(date=TOMORROW, start="06:00", end="12:00")]


def test_english_weekend_with_am_pm_range():
    assert windows("I am available on weekends from 10 am to 4 pm") == [
        AvailabilityWindow(weekday=5, start="10:00", end="16:00"),
        AvailabilityWindow(weekday=6, start="10:00", end="16:00"),
    ]


def test_two_weekdays_share_one_period():
    assert windows("somvar aur mangalvar ko shaam ko aa sakta hoon") == [
        AvailabilityWindow(weekday=0, start="16:00", end="20:00"),
        AvailabilityWindow(weekday=1, start="16:00", end="20:00"),
    ]


def test_everyday_with_hindi_time_range():
    assert windows("roz subah 8 se 11 tak") == [AvailabilityWindow(start="08:00", end="11:00")]


def test_afternoon_hours_without_am_pm_are_read_as_pm():
    assert windows("10 baje se 2 baje tak") == [AvailabilityWindow(start="10:00", end="14:00")]
    assert windows("shaam 5 baje") == [AvailabilityWindow(start="17:00", end="20:00")]


def test_negation_makes_a_busy_window_and_later_clause_inherits_the_day():
    result = parse_availability("Main kal subah free hoon lekin shaam ko nahi", TODAY)
    assert result.windows == [
        AvailabilityWindow(date=TOMORROW, start="06:00", end="12:00", available=True),
        AvailabilityWindow(date=TOMORROW, start="16:00", end="20:00", available=False),
    ]
    assert result.summary == "Free tomorrow (Sat 12 Sep) 06:00-12:00; Busy tomorrow (Sat 12 Sep) 16:00-20:00."


def test_whole_day_off_then_day_after_tomorrow_free():
    assert windows("kal nahi aa sakta, parso pura din free") == [
        AvailabilityWindow(date=TOMORROW, start="00:00", end="23:59", available=False),
        AvailabilityWindow(date=date(2026, 9, 13), start="06:00", end="20:00", available=True),
    ]


def test_english_busy_on_a_weekday():
    assert windows("busy on sunday") == [AvailabilityWindow(weekday=6, start="00:00", end="23:59", available=False)]


def test_transcript_with_no_availability_gives_nothing_and_zero_confidence():
    result = parse_availability("theek hai", TODAY)
    assert result.windows == []
    assert result.confidence == 0.0
    assert result.summary == "No availability understood."


def test_unrecognised_words_lower_confidence_but_do_not_break_parsing():
    result = parse_availability("kal subah free hoon gibberishword anotherone", TODAY)
    assert result.windows and result.unrecognised == ["gibberishword", "anotherone"]
    assert 0 < result.confidence < 1


@pytest.mark.parametrize("text, language", [
    ("kal subah free hoon", "mixed"),
    ("somvar ko aa sakta hoon", "hi"),
    ("available tomorrow morning", "en"),
    ("कल सुबह", "hi"),
    ("12345", "unknown"),
])
def test_language_detection(text, language):
    assert detect_language(text) == language


def test_describe_windows_is_human_readable():
    text = describe_windows([AvailabilityWindow(weekday=0, start="09:00", end="17:00"),
                             AvailabilityWindow(start="06:00", end="20:00", available=False)], TODAY)
    assert text == "Free every Monday 09:00-17:00; Busy every day 06:00-20:00."
