"""
The community rate card.

The general body fixes what an hour of each trade is worth — a visit charge
plus an hourly rate, with a minimum billable time — so that nobody haggles
from scratch at the door. A settlement quotes from this card (hours ×
rate + visit + materials), and the amount the two sides finally agree may
sit anywhere inside a fair band around that quote (±band_percent). Outside
the band the council decides.

Rates are public within the cooperative: a household sees the expected
price before booking, a worker sees what the job should pay, and the Sabha
edits the card after a general-body resolution.
"""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.database import connection
from app import tenancy
from app.services.ledger import paise_to_rupees, rupees_to_paise
from app.trades import CANONICAL_TRADES, canonical_trade

# visit charge, hourly rate (rupees), minimum hours — Bhopal, 2026, as the general body set them
DEFAULT_RATES: dict[str, tuple[int, int, float]] = {
    "plumbing": (150, 250, 1.0),
    "electrical": (150, 250, 1.0),
    "carpentry": (200, 300, 1.0),
    "painting": (100, 200, 2.0),
    "cleaning": (100, 150, 2.0),
}
DEFAULT_BAND_PERCENT = 25


class Rate(BaseModel):
    trade: str
    visit_charge_rupees: float
    hourly_rate_rupees: float
    min_hours: float
    band_percent: int
    note: str | None = None
    updated_at: str | None = None
    typical_hours: float | None = Field(default=None, description="median hours of the last agreed jobs of this trade")


class RateUpdate(BaseModel):
    visit_charge_rupees: Decimal | None = Field(default=None, ge=0, le=100_000, decimal_places=2)
    hourly_rate_rupees: Decimal | None = Field(default=None, gt=0, le=100_000, decimal_places=2)
    min_hours: float | None = Field(default=None, gt=0, le=24)
    band_percent: int | None = Field(default=None, ge=0, le=100)
    note: str | None = Field(default=None, max_length=300)


class Quote(BaseModel):
    """What the rate card says a job should cost, and the band the two sides may agree within."""
    trade: str
    hours_worked: float
    billable_hours: float
    visit_charge_rupees: float
    hourly_rate_rupees: float
    labour_rupees: float
    materials_rupees: float
    standard_rupees: float
    band_percent: int
    min_fair_rupees: float
    max_fair_rupees: float
    typical_hours: float | None = None
    explanation: str


def _seed(conn: sqlite3.Connection) -> None:
    coop = tenancy.tenant_id()
    for trade, (visit, hourly, min_hours) in DEFAULT_RATES.items():
        conn.execute(
            "INSERT OR IGNORE INTO standard_rates (trade, cooperative_id, visit_charge_paise, hourly_rate_paise, min_hours, band_percent) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trade, coop, visit * 100, hourly * 100, min_hours, DEFAULT_BAND_PERCENT),
        )


def _typical_hours(conn: sqlite3.Connection, trade: str, last: int = 30) -> float | None:
    hours = [
        r[0] for r in conn.execute(
            "SELECT s.hours_worked FROM settlements s JOIN bookings b ON b.id = s.booking_id "
            "WHERE b.trade = ? AND s.status = 'agreed' ORDER BY s.agreed_at DESC LIMIT ?", (trade, last)
        )
    ]
    if not hours:
        return None
    hours.sort()
    mid = len(hours) // 2
    median = hours[mid] if len(hours) % 2 else (hours[mid - 1] + hours[mid]) / 2
    return round(median * 2) / 2  # to the nearest half hour


def _model(conn: sqlite3.Connection, row: sqlite3.Row) -> Rate:
    return Rate(
        trade=row["trade"], visit_charge_rupees=paise_to_rupees(row["visit_charge_paise"]),
        hourly_rate_rupees=paise_to_rupees(row["hourly_rate_paise"]), min_hours=row["min_hours"],
        band_percent=row["band_percent"], note=row["note"], updated_at=row["updated_at"],
        typical_hours=_typical_hours(conn, row["trade"]),
    )


def get_rate(conn: sqlite3.Connection, trade: str) -> Rate:
    """The card for one trade. A trade the general body has not priced yet gets the plumbing rate as a placeholder."""
    trade = canonical_trade(trade)
    _seed(conn)
    coop = tenancy.tenant_id()
    row = conn.execute("SELECT * FROM standard_rates WHERE trade = ? AND cooperative_id = ?", (trade, coop)).fetchone()
    if row is None:
        visit, hourly, min_hours = DEFAULT_RATES["plumbing"]
        conn.execute(
            "INSERT INTO standard_rates (trade, cooperative_id, visit_charge_paise, hourly_rate_paise, min_hours, band_percent, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade, coop, visit * 100, hourly * 100, min_hours, DEFAULT_BAND_PERCENT, "Placeholder until the general body prices this trade"),
        )
        row = conn.execute("SELECT * FROM standard_rates WHERE trade = ? AND cooperative_id = ?", (trade, coop)).fetchone()
    return _model(conn, row)


def list_rates(conn: sqlite3.Connection | None = None) -> list[Rate]:
    if conn is None:
        with connection() as own:
            return list_rates(own)
    _seed(conn)
    order = {t: i for i, t in enumerate(CANONICAL_TRADES)}
    rows = [_model(conn, r) for r in conn.execute("SELECT * FROM standard_rates WHERE cooperative_id = ?", (tenancy.tenant_id(),))]
    rows.sort(key=lambda r: (order.get(r.trade, 99), r.trade))
    return rows


def update_rate(trade: str, data: RateUpdate) -> Rate:
    trade = canonical_trade(trade)
    changes: dict[str, Any] = {}
    if data.visit_charge_rupees is not None:
        changes["visit_charge_paise"] = rupees_to_paise(data.visit_charge_rupees)
    if data.hourly_rate_rupees is not None:
        changes["hourly_rate_paise"] = rupees_to_paise(data.hourly_rate_rupees)
    if data.min_hours is not None:
        changes["min_hours"] = data.min_hours
    if data.band_percent is not None:
        changes["band_percent"] = data.band_percent
    if data.note is not None:
        changes["note"] = data.note.strip() or None
    with connection() as conn:
        get_rate(conn, trade)  # ensures the row exists
        if changes:
            assignments = ", ".join(f"{column} = ?" for column in changes)
            conn.execute(
                f"UPDATE standard_rates SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE trade = ? AND cooperative_id = ?",
                (*changes.values(), trade, tenancy.tenant_id()),
            )
        return get_rate(conn, trade)


def quote(conn: sqlite3.Connection, trade: str, hours_worked: float, materials_rupees: float = 0) -> Quote:
    """Price a job from the card. Hours below the minimum bill as the minimum; materials pass through at cost."""
    rate = get_rate(conn, trade)
    billable = max(float(hours_worked), rate.min_hours)
    labour = round(billable * rate.hourly_rate_rupees, 2)
    standard = round(rate.visit_charge_rupees + labour + float(materials_rupees), 2)
    slack = round(standard * rate.band_percent / 100, 2)
    return Quote(
        trade=rate.trade, hours_worked=float(hours_worked), billable_hours=billable,
        visit_charge_rupees=rate.visit_charge_rupees, hourly_rate_rupees=rate.hourly_rate_rupees,
        labour_rupees=labour, materials_rupees=float(materials_rupees), standard_rupees=standard,
        band_percent=rate.band_percent, min_fair_rupees=round(max(1.0, standard - slack), 2), max_fair_rupees=round(standard + slack, 2),
        typical_hours=rate.typical_hours,
        explanation=(
            f"₹{rate.visit_charge_rupees:.0f} visit + {billable:g} h × ₹{rate.hourly_rate_rupees:.0f}"
            + (f" + ₹{float(materials_rupees):.0f} materials" if materials_rupees else "")
            + f" = ₹{standard:.0f}; the community allows ±{rate.band_percent}% by agreement"
        ),
    )
