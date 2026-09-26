"""
Phase D — invoicing + receipts.

  GET  /bookings/{id}/invoice   HTML invoice (PDF if weasyprint is installed) with the
                                  NPCI `upi://pay?` intent URI and the 85/10/5 split.
  POST /bookings/{id}/mark-paid  ledger-only "paid" toggle for the demo (no real money).

Money is never moved through the app: the invoice tells the customer to pay the
worker (or the cooperative) directly over UPI, and the ledger records the
trust-anchor split for accounting. `demo_mark_paid` exists only so the demo
end-to-end flow can show "paid" without an actual UPI transaction.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from app import tenancy
from app.auth import User, require_council, require_customer, require_user
from app.booking_flow_db import booking_flow_connection
from app.services.ledger import SPLIT_PERCENT, generate_upi_qr_data, paise_to_rupees

log = logging.getLogger("sahakarsetu.invoicing")
router = APIRouter(tags=["invoicing"])


def _fmt_money(paise: int) -> str:
    return f"₹{paise_to_rupees(paise):,.2f}"


def _invoice_rows(conn: sqlite3.Connection, booking_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT b.id, b.customer_name, b.customer_phone, b.trade, b.created_at, "
        "a.worker_id, w.name AS worker_name, w.phone AS worker_phone, "
        "s.agreed_paise, s.proposed_paise, s.status AS settlement_status "
        "FROM bookings b LEFT JOIN assignments a ON a.booking_id = b.id "
        "LEFT JOIN workers w ON w.id = a.worker_id "
        "LEFT JOIN settlements s ON s.booking_id = b.id "
        "WHERE b.id = ? AND b.cooperative_id = ?",
        (booking_id, tenancy.tenant_id()),
    ).fetchone()
    return dict(row) if row else None


def _amount_paise(row: dict[str, Any]) -> int:
    if row.get("agreed_paise"):
        return int(row["agreed_paise"])
    if row.get("proposed_paise"):
        return int(row["proposed_paise"])
    return 0


def render_invoice_html(ctx: dict[str, Any]) -> str:
    total = ctx["total_paise"]
    upi = generate_upi_qr_data(ctx["booking_id"], paise_to_rupees(total))
    breakdown = upi["breakdown"]
    rows = "".join(
        f'<tr><td>{party.title()}</td><td>{pct}%</td><td>{_fmt_money(share)}</td></tr>'
        for party, (pct, share) in breakdown.items()
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Invoice #{ctx['booking_id']}</title>
    <style>body{font-family:system-ui,sans-serif;margin:32px;color:#111}
    h1{font-size:22px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ddd;padding:6px 10px;text-align:left}
    .muted{color:#666;font-size:13px} .code{font-family:monospace;background:#f4f4f4;padding:2px 6px;border-radius:4px}</style></head>
    <body>
    <h1>Invoice #{ctx['booking_id']} — SahakarSetu</h1>
    <p><strong>Customer:</strong> {ctx['customer_name']}{ctx['customer_phone'] or ''} </p>
    <p><strong>Worker:</strong> {ctx['worker_name'] or '—'}  </p>
    <p><strong>Trade:</strong> {ctx['trade']}  ·  <strong>Date:</strong> {ctx['created_at'] or '—'}</p>
    <h2 style="font-size:20px">Total: {_fmt_money(total)}</h2>
    <table><thead><tr><th>Party</th><th>Share</th><th>Amount</th></tr></thead>
    <tbody>{rows}</tbody></table>
    <p class="muted">Pay the worker directly by scanning the UPI code or tapping: <span class="code">{upi['upi_uri']}</span></p>
    <p class="muted">85% goes to the worker, 10% to the cooperative welfare fund and 5% to platform operations.</p>
    </body></html>"""


@router.get("/bookings/{booking_id}/invoice")
def invoice(request: Request, booking_id: int, user: User = Depends(require_user)) -> Response:
    with booking_flow_connection() as conn:
        row = _invoice_rows(conn, booking_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    total = _amount_paise(row)
    if total <= 0:
        raise HTTPException(status_code=422, detail="Booking has no agreed price yet; complete a settlement first.")

    ctx = {**row, "total_paise": total}
    html = render_invoice_html(ctx)

    # Optional PDF rendering. weasyprint needs system libs (pango/cairo); if it
    # is unavailable the invoice is still delivered as HTML, so the flow never blocks.
    try:
        from weasyprint import HTML

        pdf = HTML(string=html, base_url=str(request.base_url)).write_pdf()
        return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=invoice-{booking_id}.pdf"})
    except Exception as exc:  # noqa: BLE001 - missing optional dependency is expected
        log.debug("weasyprint unavailable; returning HTML invoice: %s", exc)
        return HTMLResponse(content=html)


@router.post("/bookings/{booking_id}/mark-paid")
def mark_paid(booking_id: int, user: User = Depends(require_user)) -> JSONResponse:
    """Ledger-only demo toggle: records the 85/10/5 split in the payment ledger.

    No money changes hands. Real deployments replace this with a UPI callback
    webhook that credits the worker and writes the same rows.
    """
    with booking_flow_connection() as conn:
        row = conn.execute(
            "SELECT b.id, a.worker_id, s.agreed_paise, s.proposed_paise "
            "FROM bookings b LEFT JOIN assignments a ON a.booking_id = b.id "
            "LEFT JOIN settlements s ON s.booking_id = b.id "
            "WHERE b.id = ? AND b.cooperative_id = ?",
            (booking_id, tenancy.tenant_id()),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
        existing = conn.execute(
            "SELECT COUNT(*) FROM payment_ledger WHERE booking_id = ?", (booking_id,)
        ).fetchone()[0]
        if existing:
            raise HTTPException(status_code=409, detail="Invoice already marked paid.")
        total = int(row["agreed_paise"] or row["proposed_paise"] or 0)
        if total <= 0:
            raise HTTPException(status_code=422, detail="No settled amount to mark paid.")
        split = {party: total * pct // 100 for party, pct in SPLIT_PERCENT.items()}
        split["worker"] = total - (split["welfare_fund"] + split["platform_operations"])
        for party, share in split.items():
            conn.execute(
                "INSERT INTO payment_ledger (booking_id, worker_id, party, share_percent, amount_paise, cooperative_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (booking_id, row["worker_id"], party, SPLIT_PERCENT[party], share, tenancy.tenant_id()),
            )
        conn.execute(
            "UPDATE settlements SET paid_via = ? WHERE booking_id = ? AND cooperative_id = ?",
            ("upi", booking_id, tenancy.tenant_id()),
        )
    return JSONResponse({"booking_id": booking_id, "status": "paid", "split": split})
