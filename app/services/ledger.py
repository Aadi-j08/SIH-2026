"""
Mock payment ledger for completed bookings. No real money moves.

Amounts are kept in integer paise so the three shares always add up to the
exact bill. Any rounding remainder goes to the worker.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Change the split here; the parties must add up to 100.
SPLIT_PERCENT: dict[str, int] = {
    "worker": 85,
    "welfare_fund": 10,          # cooperative welfare fund
    "platform_operations": 5,
}
assert sum(SPLIT_PERCENT.values()) == 100, "Payment split must add up to 100%"


def rupees_to_paise(amount: Decimal) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def paise_to_rupees(paise: int) -> float:
    return round(paise / 100, 2)


def split_payment(amount_paise: int) -> dict[str, int]:
    """Split a bill into ledger shares. Non-worker shares round down; the worker gets the remainder."""
    if amount_paise <= 0:
        raise ValueError("amount_paise must be positive")
    shares = {
        party: amount_paise * percent // 100
        for party, percent in SPLIT_PERCENT.items()
        if party != "worker"
    }
    shares["worker"] = amount_paise - sum(shares.values())
    return {party: shares[party] for party in SPLIT_PERCENT}
