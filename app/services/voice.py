"""
Voice availability AI.

Workers tell the app when they are free by speaking. Speech-to-text runs on
the phone (the PWA uses the browser's Web Speech API), and this module turns
the transcript - Hindi, English or Hinglish, Latin or Devanagari script -
into the structured AvailabilityWindow objects the allocation engine reads.
Rule-based and fully offline: no external API, deterministic, testable.

    parse_availability("kal subah free hoon", reference_date=date(2026, 9, 11))
    -> windows=[AvailabilityWindow(date=2026-09-12, start="06:00", end="12:00")]

Understands
  days      aaj/today, kal/tomorrow, parso/day after tomorrow,
            weekday names (somvar.../monday...), roz/daily/har din, weekend
  periods   subah/morning, dopahar/afternoon, shaam/evening, raat/night,
            pura din/full day
  times     "10 baje", "10 am", "10:30", "10 se 2 tak", "10 to 2", "10-2"
  negation  nahi/nahin, busy, chutti/leave, not available, can't
  clauses   "kal subah free hoon lekin shaam ko nahi" -> one free window,
            one busy window
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.schemas import AvailabilityWindow, VoiceAvailabilityResult

# ── vocabulary ───────────────────────────────────────────────────────────

WEEKDAYS: dict[int, tuple[str, ...]] = {
    0: ("monday", "mon", "somvar", "somwar", "somvaar", "सोमवार", "सोम"),
    1: ("tuesday", "tue", "tues", "mangalvar", "mangalwar", "mangal", "मंगलवार", "मंगल"),
    2: ("wednesday", "wed", "budhvar", "budhwar", "budh", "बुधवार", "बुध"),
    3: ("thursday", "thu", "thurs", "guruvar", "guruwar", "guru", "brihaspativar", "गुरुवार", "गुरु"),
    4: ("friday", "fri", "shukravar", "shukrawar", "shukra", "jumma", "शुक्रवार", "शुक्र"),
    5: ("saturday", "sat", "shanivar", "shaniwar", "shani", "शनिवार", "शनि"),
    6: ("sunday", "sun", "ravivar", "raviwar", "ravi", "itvar", "itwar", "रविवार", "रवि", "इतवार"),
}
WEEKDAY_WORDS = {word: weekday for weekday, words in WEEKDAYS.items() for word in words}
RELATIVE_DAYS: dict[str, int] = {
    "aaj": 0, "aj": 0, "आज": 0, "today": 0, "tonight": 0, "tody": 0, "todya": 0,
    "kal": 1, "kaal": 1, "कल": 1, "tomorrow": 1, "tmrw": 1,
    "tommorrow": 1, "tommorow": 1, "tomorow": 1, "tomorro": 1, "tommrow": 1,   # common misspellings
    "parso": 2, "parson": 2, "परसों": 2, "dayaftertomorrow": 2,
}
EVERYDAY = {"roz", "roj", "रोज़", "रोज", "daily", "everyday", "hamesha", "हमेशा", "always", "fullweek"}
WEEKEND = {"weekend", "weekends", "वीकेंड"}
RANGE_WORDS = {"se", "to", "tak", "till", "until", "through", "से"}
PERIODS: dict[str, tuple[str, str]] = {
    "morning": ("06:00", "12:00"), "subah": ("06:00", "12:00"), "subha": ("06:00", "12:00"),
    "savere": ("06:00", "12:00"), "सुबह": ("06:00", "12:00"), "सवेरे": ("06:00", "12:00"),
    "afternoon": ("12:00", "16:00"), "dopahar": ("12:00", "16:00"), "dopehar": ("12:00", "16:00"),
    "dupahar": ("12:00", "16:00"), "दोपहर": ("12:00", "16:00"),
    "evening": ("16:00", "20:00"), "shaam": ("16:00", "20:00"), "sham": ("16:00", "20:00"),
    "shyam": ("16:00", "20:00"), "शाम": ("16:00", "20:00"),
    "night": ("20:00", "23:59"), "raat": ("20:00", "23:59"), "rat": ("20:00", "23:59"), "रात": ("20:00", "23:59"),
    "fullday": ("06:00", "20:00"),
}
_PERIOD_NAME = {"06:00": "morning", "12:00": "afternoon", "16:00": "evening", "20:00": "night"}
NEGATIVE = {
    "nahi", "nahin", "nai", "नहीं", "नही", "not", "busy", "vyast", "व्यस्त", "chutti", "chhutti",
    "छुट्टी", "leave", "unavailable", "cant", "cannot", "mat", "off", "band", "बंद", "nope", "no",
}
AVAILABLE_WORDS = {
    "free", "available", "khali", "khaali", "फ्री", "खाली", "उपलब्ध", "aaunga", "aaungi", "aa", "aana",
    "milega", "kaam", "work", "come", "milunga", "milungi", "rahunga", "rahungi",
}
FILLER = {
    "main", "mai", "mein", "me", "i", "im", "hoon", "hu", "hun", "hai", "ho", "hain", "ke", "ki", "ka", "ko",
    "se", "tak", "par", "pe", "aur", "and", "or", "ya", "kar", "karunga", "karungi", "sakta", "sakti",
    "sakte", "will", "be", "can", "am", "pm", "on", "at", "in", "the", "for", "a", "to", "from", "day",
    "din", "time", "baje", "बजे", "hoga", "मैं", "हूँ", "हूं", "को", "से", "तक", "और", "काम", "मुझे", "है",
    "हैं", "liye", "ok", "theek", "thik", "haan", "ji", "bhi", "sirf", "only", "just", "oclock",
}
KNOWN = (
    set(WEEKDAY_WORDS) | set(RELATIVE_DAYS) | EVERYDAY | WEEKEND | set(PERIODS) | NEGATIVE
    | AVAILABLE_WORDS | FILLER
)
ENGLISH_WORDS = {
    "today", "tonight", "tomorrow", "morning", "afternoon", "evening", "night", "daily", "everyday",
    "always", "weekend", "weekends", "busy", "available", "free", "not", "am", "pm", "leave", "off",
    "i", "im", "on", "at", "from", "to", "the", "and", "can", "will", "work", "come", "day", "only",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "mon", "tue", "wed", "thu", "fri", "sat", "sun",
}
HINDI_WORDS = KNOWN - ENGLISH_WORDS - {"a", "in", "for", "be", "or", "me", "time", "ok", "just", "oclock"}

# Multi-word expressions collapsed to one token before tokenising.
PHRASES: tuple[tuple[str, str], ...] = (
    ("day after tomorrow", "dayaftertomorrow"),
    ("full day", "fullday"), ("whole day", "fullday"), ("all day", "fullday"), ("entire day", "fullday"),
    ("pura din", "fullday"), ("poora din", "fullday"), ("pure din", "fullday"), ("saara din", "fullday"),
    ("पूरा दिन", "fullday"), ("पूरे दिन", "fullday"),
    ("har din", "roz"), ("हर दिन", "roz"), ("every day", "roz"), ("pure hafte", "fullweek"),
    ("whole week", "fullweek"), ("all week", "fullweek"), ("पूरे हफ़्ते", "fullweek"),
    ("not available", "nahi"), ("not free", "nahi"), ("can not", "nahi"), ("can't", "nahi"),
    ("cannot", "nahi"), ("on leave", "chutti"), ("day off", "chutti"),
    ("a.m.", "am"), ("p.m.", "pm"), ("o'clock", "oclock"),
)
CLAUSE_SPLIT = re.compile(r"[,;.!?]|\b(?:lekin|but|magar|parantu|however|except|लेकिन|मगर|परंतु)\b")
TIME_MARK = r"(?:am|pm|baje|बजे|oclock)"
TIME_RANGE = re.compile(   # (?<![\d-]) / (?![\d-]) keep "09-12" inside "2026-09-12" from reading as a time range
    rf"(?<![\d-])\b(\d{{1,2}})(?::(\d{{2}}))?\s*({TIME_MARK})?\s*(?:se|to|-|–|till|until|tak|and|aur)\s*"
    rf"(\d{{1,2}})(?::(\d{{2}}))?(?![\d-])\s*({TIME_MARK})?"
)
TIME_SINGLE = re.compile(rf"(?<![\d-])\b(\d{{1,2}})(?::(\d{{2}}))?\s*({TIME_MARK})\b")
TIME_AT = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?(?!\d)")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
TOKEN = re.compile(r"[a-zऀ-ॿ]+|\d{1,2}(?::\d{2})?")

WORKING_DAY = ("06:00", "20:00")
ANY_TIME = ("00:00", "23:59")
DEFAULT_END = "20:00"


# ── parsing ──────────────────────────────────────────────────────────────

def _prepare(text: str) -> str:
    text = text.lower().replace("’", "'")
    for phrase, token in PHRASES:
        text = text.replace(phrase, token)
    return text


def _to_24h(hour: int, minute: int, marker: str | None, period: str | None) -> str:
    if marker == "am":
        hour = 0 if hour == 12 else hour
    elif marker == "pm":
        hour = hour if hour == 12 else hour + 12
    elif period in ("afternoon", "evening", "night") and hour < 12:
        hour += 12
    elif period is None and hour < 7:      # "2 baje" means 14:00; nobody offers 2 am
        hour += 12
    return f"{min(hour, 23):02d}:{min(minute, 59):02d}"


def _ampm(marker: str | None) -> str | None:
    return marker if marker in ("am", "pm") else None


def _times(clause: str, period_key: str | None) -> tuple[str, str] | None:
    """Explicit time range or single start time in the clause, as (start, end)."""
    period = _PERIOD_NAME.get(PERIODS[period_key][0]) if period_key else None
    match = TIME_RANGE.search(clause)
    if match:
        h1, m1, mark1, h2, m2, mark2 = match.groups()
        start = _to_24h(int(h1), int(m1 or 0), _ampm(mark1), period)
        end = _to_24h(int(h2), int(m2 or 0), _ampm(mark2), period)
        if end <= start and int(h2) < 12 and _ampm(mark2) is None:   # "10 se 2" -> 10:00-14:00
            end = f"{int(h2) + 12:02d}:{int(m2 or 0):02d}"
        return (start, end) if end > start else None
    match = TIME_SINGLE.search(clause) or TIME_AT.search(clause)
    if match:
        groups = match.groups()
        h, m, mark = (groups + (None,))[:3]
        start = _to_24h(int(h), int(m or 0), _ampm(mark), period)
        end = PERIODS[period_key][1] if period_key else DEFAULT_END
        return start, (end if end > start else "23:59")
    return None


DaySpec = tuple[date | None, int | None]


def _day_specs(tokens: list[str], reference: date) -> list[DaySpec] | None:
    """Days named in the clause; None when the clause names no day at all."""
    if any(t in EVERYDAY for t in tokens):
        return [(None, None)]
    specs: list[DaySpec] = []
    for i, token in enumerate(tokens):
        spec: DaySpec | None = None
        if token in RELATIVE_DAYS:
            spec = (reference + timedelta(days=RELATIVE_DAYS[token]), None)
        elif token in WEEKDAY_WORDS:
            spec = (None, WEEKDAY_WORDS[token])
            # "somvar se shukravar" / "monday to friday": every weekday from the first to the second
            if i >= 2 and tokens[i - 1] in RANGE_WORDS and tokens[i - 2] in WEEKDAY_WORDS:
                first, last = WEEKDAY_WORDS[tokens[i - 2]], WEEKDAY_WORDS[token]
                span = range(first, last + 1) if first <= last else [*range(first, 7), *range(0, last + 1)]
                for weekday in span:
                    if (None, weekday) not in specs:
                        specs.append((None, weekday))
                continue
        if spec is not None and spec not in specs:
            specs.append(spec)
    if any(t in WEEKEND for t in tokens):
        specs.extend(s for s in ((None, 5), (None, 6)) if s not in specs)
    return specs or None


def _parse_clause(
    clause: str, reference: date, inherited_days: list[DaySpec] | None,
) -> tuple[list[AvailabilityWindow], list[str], int, list[DaySpec] | None, list[str]]:
    """Windows for one clause. A clause that names no day inherits the previous clause's days,
    so "kal subah free hoon lekin shaam ko nahi" makes tomorrow evening busy, not every evening.
    The last item lists what the parser assumed (no day named, only a start time) so the app can
    say so before the worker saves."""
    tokens = TOKEN.findall(clause)
    assumptions: list[str] = []
    if not tokens:
        return [], [], 0, inherited_days, assumptions
    unrecognised = [t for t in tokens if t not in KNOWN and not t[0].isdigit()]
    negated = any(t in NEGATIVE for t in tokens)
    period_keys = list(dict.fromkeys(t for t in tokens if t in PERIODS))
    explicit = _times(clause, period_keys[0] if period_keys else None)
    days = _day_specs(tokens, reference)
    has_intent = negated or any(t in AVAILABLE_WORDS for t in tokens)
    if not (days or period_keys or explicit or has_intent):
        return [], unrecognised, len(tokens), inherited_days, assumptions   # "theek hai" says nothing about availability
    if not days and not inherited_days:
        assumptions.append("No day was named, so this was taken as every day. Say 'kal', 'somvar' or 'today' to be exact.")
    days = days or inherited_days or [(None, None)]

    if explicit and not TIME_RANGE.search(clause):
        assumptions.append(f"Only a start time was heard, so it runs until {explicit[1]}. Say 'se ... tak' or 'from ... to' for an end time.")
    if explicit:
        slots = [explicit]
    elif period_keys:
        slots = list(dict.fromkeys(PERIODS[k] for k in period_keys))
    else:
        slots = [ANY_TIME if negated else WORKING_DAY]
    windows = [
        AvailabilityWindow(date=day, weekday=weekday, start=start, end=end, available=not negated)
        for day, weekday in days
        for start, end in slots
    ]
    return windows, unrecognised, len(tokens), days, assumptions


def detect_language(text: str) -> str:
    if DEVANAGARI.search(text):
        return "hi"
    tokens = set(TOKEN.findall(text.lower()))
    hindi, english = bool(tokens & HINDI_WORDS), bool(tokens & ENGLISH_WORDS)
    if hindi and english:
        return "mixed"
    return "hi" if hindi else "en" if english else "unknown"


def parse_availability(transcript: str, reference_date: date | None = None) -> VoiceAvailabilityResult:
    """Turn a spoken availability sentence into AvailabilityWindow objects."""
    reference = reference_date or date.today()
    windows: list[AvailabilityWindow] = []
    unrecognised: list[str] = []
    assumptions: list[str] = []
    total_tokens = 0
    days: list[DaySpec] | None = None
    for clause in CLAUSE_SPLIT.split(_prepare(transcript)):
        clause_windows, clause_unknown, count, days, assumed = _parse_clause(clause, reference, days)
        windows.extend(w for w in clause_windows if w not in windows)
        unrecognised.extend(clause_unknown)
        assumptions.extend(a for a in assumed if a not in assumptions)
        total_tokens += count

    if not windows or total_tokens == 0:
        confidence = 0.0
    else:
        confidence = round(0.4 + 0.6 * (total_tokens - len(unrecognised)) / total_tokens, 2)
        if any(a.startswith("No day") for a in assumptions):
            confidence = min(confidence, 0.5)   # a guessed day is never a confident parse
    return VoiceAvailabilityResult(
        transcript=transcript,
        language=detect_language(transcript),
        windows=windows,
        confidence=confidence,
        summary=describe_windows(windows, reference),
        unrecognised=unrecognised,
        assumptions=assumptions,
    )


# ── presentation ─────────────────────────────────────────────────────────

_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def describe_windows(windows: list[AvailabilityWindow], reference: date | None = None) -> str:
    """Human-readable summary, e.g. 'Free tomorrow (Fri 12 Sep) 06:00-12:00; busy every Sunday 00:00-23:59.'"""
    if not windows:
        return "No availability understood."
    reference = reference or date.today()
    parts = []
    for w in windows:
        if w.date is not None:
            relative = {0: "today", 1: "tomorrow", 2: "day after tomorrow"}.get((w.date - reference).days)
            when = f"{relative} ({w.date.strftime('%a %d %b')})" if relative else f"on {w.date.strftime('%a %d %b')}"
        elif w.weekday is not None:
            when = f"every {_DAY_NAMES[w.weekday]}"
        else:
            when = "every day"
        parts.append(f"{'Free' if w.available else 'Busy'} {when} {w.start}-{w.end}")
    return "; ".join(parts) + "."
