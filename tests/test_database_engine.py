"""
Tests for Dual-Database Engine Configuration and Schema Integrity.
"""
from app.database import get_database_engine_info, connection


def test_database_engine_info():
    info = get_database_engine_info()
    assert "engine" in info
    assert info["engine"] in ("SQLite", "PostgreSQL")
    assert "concurrency" in info


def test_core_tables_and_indexes_exist(db_path):
    with connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "workers" in tables
        assert "bookings" in tables
        assert "assignments" in tables
        assert "users" in tables
        assert "disputes" in tables
        assert "settlements" in tables
