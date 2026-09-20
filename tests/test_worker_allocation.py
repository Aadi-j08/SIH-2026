"""
Tests for Smart Worker Allocation and Fair Batch Dispatch Engine.
"""
from app.services.worker_allocation import calculate_match_score, match_batch_jobs


def test_calculate_match_score_prefers_fairness_for_idle_workers():
    busy_worker = {
        "id": 1,
        "name": "Ramesh",
        "latitude": 23.18,
        "longitude": 77.42,
        "jobs_this_week": 10,
        "rating": 4.8,
        "status": "active",
    }
    idle_worker = {
        "id": 2,
        "name": "Suresh",
        "latitude": 23.18,
        "longitude": 77.42,
        "jobs_this_week": 0,
        "rating": 4.5,
        "status": "active",
    }
    booking = {
        "id": 101,
        "latitude": 23.18,
        "longitude": 77.42,
    }

    score_busy = calculate_match_score(busy_worker, booking)
    score_idle = calculate_match_score(idle_worker, booking)

    # Idle worker should get higher or competitive score due to fairness weighting
    assert score_idle > score_busy


def test_match_batch_jobs_distributes_equitably():
    workers = [
        {"id": 1, "name": "Worker A", "trade": "plumber", "latitude": 23.18, "longitude": 77.42, "jobs_this_week": 5, "rating": 4.5},
        {"id": 2, "name": "Worker B", "trade": "plumber", "latitude": 23.185, "longitude": 77.425, "jobs_this_week": 1, "rating": 4.2},
    ]
    bookings = [
        {"id": 101, "customer_name": "Customer 1", "trade": "plumber", "latitude": 23.18, "longitude": 77.42},
        {"id": 102, "customer_name": "Customer 2", "trade": "plumber", "latitude": 23.185, "longitude": 77.425},
    ]

    result = match_batch_jobs(bookings, workers)
    assert result["matched_count"] == 2
    assigned_worker_ids = {a["worker_id"] for a in result["assignments"]}
    assert assigned_worker_ids == {1, 2}
    assert len(result["unassigned_bookings"]) == 0
