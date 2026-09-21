"""
Unit tests for Gemini Vision Proof-of-Work Verifier and Cryptographic SHA-256 Ledger Hash Chain.
"""
from app.services.vision_verifier import verify_repair_photos
from app.services.ledger import (
    GENESIS_HASH,
    audit_ledger_chain,
    compute_transaction_hash,
)
from app import database
from app.booking_flow_db import booking_flow_connection


def test_vision_verifier_offline_heuristics_both_photos():
    start_photo = "data:image/jpeg;base64," + "A" * 100
    end_photo = "data:image/jpeg;base64," + "B" * 100

    res = verify_repair_photos(trade="plumbing", start_photo_data=start_photo, end_photo_data=end_photo)
    assert res["verified"] is True
    assert res["confidence"] >= 0.80
    assert res["trade_matched"] is True


def test_vision_verifier_missing_both_photos():
    res = verify_repair_photos(trade="electrical", start_photo_data=None, end_photo_data=None)
    assert res["verified"] is False
    assert "missing_both_photos" in res["flags"]


def test_ledger_sha256_hash_chain_computation():
    h1 = compute_transaction_hash(
        prev_hash=GENESIS_HASH,
        booking_id=101,
        worker_id=5,
        party="worker",
        amount_paise=34000,
        created_at="2026-09-21T10:00:00",
    )
    assert len(h1) == 64
    assert h1 != GENESIS_HASH

    h2 = compute_transaction_hash(
        prev_hash=h1,
        booking_id=101,
        worker_id=None,
        party="welfare_fund",
        amount_paise=4000,
        created_at="2026-09-21T10:00:00",
    )
    assert len(h2) == 64
    assert h2 != h1


def test_audit_ledger_chain_on_database():
    database.init_db()
    with booking_flow_connection() as conn:
        res = audit_ledger_chain(conn)
        assert res["intact"] is True
        assert res["cryptographic_algorithm"] == "SHA-256 Recursive Chain"
        assert res["total_transactions"] >= 0
