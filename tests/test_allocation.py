"""Fair allocation engine."""
from __future__ import annotations

from datetime import datetime

import pytest

from app.schemas import AvailabilityWindow, ServiceRequest, WorkerProfile
from app.services.allocation import WEIGHTS, availability_status, haversine_km, recommend_workers

SITE = (23.1800, 77.4200)
SLOT = datetime(2026, 9, 12, 10, 0)  # a Saturday


def worker(id, name, trade="plumbing", lat=SITE[0], lon=SITE[1], jobs=0, rating=None, availability=()):
    return WorkerProfile(id=id, name=name, trade=trade, latitude=lat, longitude=lon,
                         jobs_this_week=jobs, rating=rating, availability=list(availability))


def request(trade="plumbing", scheduled_for=SLOT, **kwargs):
    return ServiceRequest(trade=trade, latitude=SITE[0], longitude=SITE[1], scheduled_for=scheduled_for, **kwargs)


def test_haversine_is_zero_at_same_point_and_about_111km_per_degree():
    assert haversine_km(*SITE, *SITE) == 0
    assert haversine_km(23.0, 77.0, 24.0, 77.0) == pytest.approx(111.2, abs=0.5)


def test_weights_add_up_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def test_only_matching_trade_is_considered_case_insensitively():
    ranked = recommend_workers(request("Plumbing"), [worker(1, "Asha", "plumbing"), worker(2, "Meena", "electrical")])
    assert [r.worker_id for r in ranked] == [1]


def test_empty_pool_returns_empty_list_not_error():
    assert recommend_workers(request(), []) == []
    assert recommend_workers(request(), [worker(1, "Meena", "electrical")]) == []


def test_fairness_prefers_worker_with_fewest_jobs_when_otherwise_equal():
    ranked = recommend_workers(request(), [worker(1, "Busy", jobs=6), worker(2, "Idle", jobs=0)])
    assert ranked[0].worker_id == 2
    assert ranked[0].score_breakdown["fairness"] == 1.0
    assert ranked[1].score_breakdown["fairness"] == 0.0
    assert "fewest in the pool" in ranked[0].explanation
    assert "fewest jobs this week (0)" in ranked[0].why_selected


def test_recommendation_exposes_explainable_selection_reasons():
    ranked = recommend_workers(request(), [worker(1, "Asha", jobs=0, rating=4.5)])
    assert ranked[0].why_selected == [
        "within the 15 km service radius (0.0 km away)",
        "fewest jobs this week (0)",
        "rated 4.5/5",
        "no conflicting availability declared",
    ]


def test_nearer_worker_wins_when_fairness_and_rating_are_equal():
    far = worker(1, "Far", lat=SITE[0] + 0.05)   # ~5.5 km north
    near = worker(2, "Near")
    ranked = recommend_workers(request(), [far, near])
    assert ranked[0].worker_id == 2
    assert ranked[0].distance_km == 0.0
    assert ranked[1].distance_km == pytest.approx(5.56, abs=0.05)


def test_workers_beyond_max_distance_are_excluded():
    ranked = recommend_workers(request(max_distance_km=2.0), [worker(1, "Far", lat=SITE[0] + 0.05)])
    assert ranked == []


def test_unrated_worker_gets_neutral_rating_score():
    ranked = recommend_workers(request(), [worker(1, "New"), worker(2, "Star", rating=5.0)])
    scores = {r.worker_id: r.score_breakdown["rating"] for r in ranked}
    assert scores == {1: 0.5, 2: 1.0}


def test_declared_busy_worker_is_skipped_and_declared_free_worker_scores_higher():
    busy = worker(1, "Busy", availability=[AvailabilityWindow(date=SLOT.date(), start="06:00", end="20:00", available=False)])
    free = worker(2, "Free", availability=[AvailabilityWindow(weekday=SLOT.weekday(), start="09:00", end="12:00")])
    unknown = worker(3, "Unknown")
    ranked = recommend_workers(request(), [busy, free, unknown])
    assert [r.worker_id for r in ranked] == [2, 3]
    assert ranked[0].score_breakdown["availability"] == 1.0
    assert ranked[1].score_breakdown["availability"] == 0.7


def test_availability_status_rules():
    saturday_morning = [AvailabilityWindow(weekday=5, start="06:00", end="12:00")]
    assert availability_status(saturday_morning, SLOT) == "available"
    assert availability_status(saturday_morning, SLOT.replace(hour=15)) == "unavailable"   # declared that day, not that slot
    assert availability_status(saturday_morning, datetime(2026, 9, 14, 10)) == "unknown"     # said nothing about Monday
    assert availability_status([], SLOT) == "unknown"
    assert availability_status(saturday_morning, None) == "unknown"


def test_scores_are_bounded_ranked_and_explained():
    pool = [worker(1, "A", jobs=2, rating=4.0), worker(2, "B", jobs=0, rating=3.5, lat=SITE[0] + 0.01), worker(3, "C", jobs=5)]
    ranked = recommend_workers(request(), pool, top_k=2)
    assert len(ranked) == 2
    assert [r.rank for r in ranked] == [1, 2]
    assert ranked[0].score >= ranked[1].score
    for r in ranked:
        assert 0 <= r.score <= 1
        assert set(r.score_breakdown) == set(WEIGHTS)
        assert r.explanation.endswith(".")
