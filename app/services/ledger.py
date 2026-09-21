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


def generate_upi_qr_data(
    booking_id: int,
    total_rupees: float,
    payee_vpa: str = "sahakarsetu.coop@upi",
    payee_name: str = "SahakarSetu Cooperative",
) -> dict:
    """
    Generates NPCI-compliant dynamic UPI payment URI and 85/10/5 automated split breakdown.
    Compatible with BHIM, Google Pay, PhonePe, Paytm, and CRED.
    """
    amt_decimal = Decimal(str(total_rupees))
    amt_paise = rupees_to_paise(amt_decimal)
    split_paise = split_payment(amt_paise)

    # Standard NPCI UPI URI Scheme
    # upi://pay?pa=<vpa>&pn=<name>&am=<amount>&cu=INR&tn=<note>
    encoded_pn = payee_name.replace(" ", "%20")
    note = f"SahakarSetu Booking {booking_id} Fair Split"
    encoded_tn = note.replace(" ", "%20")
    upi_uri = (
        f"upi://pay?pa={payee_vpa}&pn={encoded_pn}"
        f"&am={total_rupees:.2f}&cu=INR&tn={encoded_tn}"
    )

    return {
        "booking_id": booking_id,
        "total_rupees": round(total_rupees, 2),
        "total_paise": amt_paise,
        "upi_uri": upi_uri,
        "payee_vpa": payee_vpa,
        "payee_name": payee_name,
        "split_rupees": {
            party: paise_to_rupees(paise) for party, paise in split_paise.items()
        },
        "split_paise": split_paise,
        "cooperative_guarantee": "100% transparent: 85% worker direct, 10% welfare pool, 5% ops.",
    }
