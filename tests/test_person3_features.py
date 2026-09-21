"""
Tests for Person 3 Deliverables (SIH 2026):
1. Urgency-weighted Bipartite Dispatch
2. Start Work & Photo Proof-of-Work (Arrival Selfie + Completion Photo)
3. Dynamic UPI Split QR Generation
4. Payment Discrepancy & Cash Bypass Auditing
5. Database Migration 4 (urgency_level + proof-of-work columns)
"""
import pytest
from app.services.worker_allocation import calculate_match_score, match_batch_jobs
from app.services.ledger import generate_upi_qr_data, split_payment
from app.services.dispute_advisor import analyze_payment_discrepancy


def test_urgency_weighted_dispatch_shifts_weights():
    """Validates that 'urgent' bookings shift weight heavily towards proximity (70%)."""
    near_worker = {
        "id": 1,
        "name": "Ramesh",
        "trade": "plumber",
        "latitude": 23.2500,
        "longitude": 77.4100,
        "jobs_this_week": 8, # Busy this week
        "rating": 4.5,
        "status": "active",
    }
    far_worker = {
        "id": 2,
        "name": "Suresh",
        "trade": "plumber",
        "latitude": 23.3200, # Farther away (approx 9km)
        "longitude": 77.4100,
        "jobs_this_week": 0, # Idle this week (high fairness)
        "rating": 4.5,
        "status": "active",
    }
    customer_booking = {
        "id": 101,
        "trade": "plumber",
        "latitude": 23.2510, # Very close to Ramesh (0.1km)
        "longitude": 77.4105,
    }

    # Standard booking: fairness gives far_worker a competitive boost
    std_booking = {**customer_booking, "urgency_level": "medium"}
    score_near_std = calculate_match_score(near_worker, std_booking)
    score_far_std = calculate_match_score(far_worker, std_booking)

    # Urgent booking: proximity dominance means near_worker wins decisively
    urgent_booking = {**customer_booking, "urgency_level": "urgent"}
    score_near_urg = calculate_match_score(near_worker, urgent_booking)
    score_far_urg = calculate_match_score(far_worker, urgent_booking)

    assert score_near_urg > score_far_urg, "Nearby worker must win in emergency dispatch"
    assert score_near_urg > score_near_std, "Urgent score should be higher for immediate proximity"


def test_upi_qr_generation_format_and_split():
    """Validates NPCI standard UPI URI format and exact 85/10/5 split."""
    data = generate_upi_qr_data(
        booking_id=42,
        total_rupees=500.0,
        payee_vpa="coop.bhopal@upi",
        payee_name="SahakarSetu Bhopal",
    )

    assert data["booking_id"] == 42
    assert data["total_rupees"] == 500.0
    assert "upi://pay?" in data["upi_uri"]
    assert "pa=coop.bhopal@upi" in data["upi_uri"]
    assert "am=500.00" in data["upi_uri"]
    assert data["split_rupees"]["worker"] == 425.0
    assert data["split_rupees"]["welfare_fund"] == 50.0
    assert data["split_rupees"]["platform_operations"] == 25.0


def test_payment_discrepancy_analysis():
    """Validates automated detection of cash bypass / overcharging."""
    # Case 1: Worker collected ₹700 cash when standard was ₹450
    result = analyze_payment_discrepancy(
        booking_id=12,
        customer_paid_rupees=700.0,
        worker_reported_rupees=450.0,
        standard_rate_rupees=400.0,
        materials_rupees=50.0,
        customer_notes="Worker asked for 700 cash on personal scanner and was rude",
    )

    assert result["is_discrepancy"] is True
    assert result["variance_rupees"] == 250.0
    assert result["escalate_to_council"] is True
    assert "excess cash" in result["recommended_action"]


def test_payment_exact_match_no_discrepancy():
    """Validates clean transaction when payment matches recorded bill."""
    result = analyze_payment_discrepancy(
        booking_id=14,
        customer_paid_rupees=450.0,
        worker_reported_rupees=450.0,
        standard_rate_rupees=400.0,
        materials_rupees=50.0,
        customer_notes="Bahut badhiya kaam kiya time pe",
    )

    assert result["is_discrepancy"] is False
    assert result["variance_rupees"] == 0.0
    assert "matches records exactly" in result["recommended_action"]
