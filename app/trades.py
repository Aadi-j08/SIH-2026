"""
Canonical trade names.

People type "plumber", "Plumbing" or "pipe repair"; the engine, the database
and the forecast all need the same word. `canonical_trade()` maps every
known spelling to one of CANONICAL_TRADES and is applied at the API
boundary (pydantic validators in app/schemas.py), so storage, matching and
filtering always see the canonical value. Unknown trades pass through
lower-cased and trimmed rather than being rejected, so a new trade can be
introduced without a code change.
"""
from __future__ import annotations

import re

CANONICAL_TRADES: tuple[str, ...] = ("plumbing", "electrical", "carpentry", "painting", "cleaning")

# alias (lower-case) -> canonical. Keep aliases lower-case, single-spaced.
TRADE_ALIASES: dict[str, str] = {
    # plumbing
    "plumbing": "plumbing", "plumber": "plumbing", "plumbers": "plumbing", "pipe repair": "plumbing",
    "pipe fitting": "plumbing", "pipefitter": "plumbing", "plumbing work": "plumbing", "nal": "plumbing",
    # electrical
    "electrical": "electrical", "electrician": "electrical", "electricians": "electrical", "wiring": "electrical",
    "electric": "electrical", "electrical work": "electrical", "bijli": "electrical",
    # carpentry
    "carpentry": "carpentry", "carpenter": "carpentry", "carpenters": "carpentry", "woodwork": "carpentry",
    "furniture repair": "carpentry", "badhai": "carpentry",
    # painting
    "painting": "painting", "painter": "painting", "painters": "painting", "wall painting": "painting",
    "house painting": "painting",
    # cleaning
    "cleaning": "cleaning", "cleaner": "cleaning", "cleaners": "cleaning", "house cleaning": "cleaning",
    "deep cleaning": "cleaning", "housekeeping": "cleaning", "safai": "cleaning",
}

_SPACES = re.compile(r"[\s_\-]+")


def _key(text: str) -> str:
    return _SPACES.sub(" ", text.strip().lower())


def canonical_trade(text: str) -> str:
    """Map any known spelling to its canonical trade; unknown trades come back lower-cased and trimmed."""
    key = _key(text)
    if key in TRADE_ALIASES:
        return TRADE_ALIASES[key]
    # "plumbing services", "electrician needed": first alias word wins
    for token in key.split(" "):
        if token in TRADE_ALIASES:
            return TRADE_ALIASES[token]
    return key


def is_canonical(text: str) -> bool:
    return text in CANONICAL_TRADES
