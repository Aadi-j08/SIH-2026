"""
Tests for AI Dispute Resolution Advisor & Sentiment Analysis Service.
"""
from app.services.dispute_advisor import (
    analyze_sentiment,
    calculate_fair_settlement,
    generate_ai_dispute_recommendation,
)


def test_sentiment_analysis_positive_review():
    res = analyze_sentiment("Bahut badhiya kaam kiya, time pe aaye aur clean work.")
    assert res["label"] == "positive"
    assert res["polarity"] > 0
    assert res["requires_council_review"] is False


def test_sentiment_analysis_negative_review():
    res = analyze_sentiment("Very bad experience, extremely rude and broken tap.")
    assert res["label"] == "negative"
    assert res["polarity"] < 0
    assert res["requires_council_review"] is True


def test_calculate_fair_settlement_midpoint():
    res = calculate_fair_settlement(proposed_rupees=600.0, counter_rupees=400.0, materials_rupees=100.0)
    # Materials = 100, Labor proposed = 500, Labor counter = 300 -> Labor compromise = 400 -> Total = 500
    assert res["suggested_settlement_inr"] == 500.0
    assert res["materials_cost_inr"] == 100.0


def test_generate_ai_dispute_recommendation_offline():
    dispute_data = {
        "kind": "payment",
        "worker_name": "Karan",
        "customer_name": "Sunita",
        "settlement_proposed_rupees": 550.0,
        "settlement_counter_rupees": 450.0,
        "description": "Extra pipes required for installation",
    }
    rec = generate_ai_dispute_recommendation(dispute_data)
    assert rec["settlement_breakdown"]["suggested_settlement_inr"] == 500.0
    assert "Recommended Settlement" in rec["recommended_resolution_note"]
