"""
Tests for Machine Learning Demand & Price Forecasting Service.
"""
from app.services.demand_forecast import DemandForecaster, forecaster


def test_forecaster_initialization():
    fc = DemandForecaster()
    assert hasattr(fc, "predict_7_day_demand")
    assert fc.predict_daily_demand(0, 0, 9) >= 1


def test_predict_7_day_demand_plumber():
    result = forecaster.predict_7_day_demand(trade="plumber", ward_id="Ward-4")
    assert result["trade"] == "plumber"
    assert result["ward_id"] == "Ward-4"
    assert len(result["daily_forecast"]) == 7
    assert result["total_7d_predicted_bookings"] > 0
    assert "RidgeRegression" in result["model_type"]


def test_pricing_bands_and_fair_rates():
    result = forecaster.predict_7_day_demand(trade="electrician", ward_id=1)
    daily = result["daily_forecast"]
    for day in daily:
        assert day["floor_rate_inr"] > 0
        assert day["recommended_rate_inr"] >= day["floor_rate_inr"]
        assert "predicted_bookings" in day
        assert day["predicted_bookings"] >= 1
