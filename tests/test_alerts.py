"""
tests/test_alerts.py — Alert service unit tests
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from alert_service import check_alerts, THRESHOLDS


def make_weather(**overrides):
    base = {
        "location": "TestCity",
        "temperature": 25.0,
        "wind_speed": 10.0,
        "rain_1h": 0.0,
        "visibility": 10000,
        "condition_id": 800,
        "demo": False,
    }
    base.update(overrides)
    return base


class TestAlertRules:
    def test_normal_conditions_no_alert(self):
        result = check_alerts(make_weather())
        assert result["alert"] is False
        assert result["severity"] == "INFO"

    def test_thunderstorm_triggers_high(self):
        result = check_alerts(make_weather(condition_id=211))
        assert result["alert"] is True
        assert result["severity"] == "HIGH"
        types = [a["type"] for a in result["alerts"]]
        assert "thunderstorm" in types

    def test_heavy_rain_triggers_warning(self):
        result = check_alerts(make_weather(rain_1h=10.0))
        assert result["alert"] is True
        types = [a["type"] for a in result["alerts"]]
        assert "heavy_rain" in types

    def test_extreme_heat_triggers_warning(self):
        result = check_alerts(make_weather(temperature=43.0))
        assert result["alert"] is True
        types = [a["type"] for a in result["alerts"]]
        assert "extreme_heat" in types

    def test_extreme_cold_triggers_warning(self):
        result = check_alerts(make_weather(temperature=3.0))
        assert result["alert"] is True
        types = [a["type"] for a in result["alerts"]]
        assert "extreme_cold" in types

    def test_strong_wind_triggers_warning(self):
        result = check_alerts(make_weather(wind_speed=60.0))
        assert result["alert"] is True
        types = [a["type"] for a in result["alerts"]]
        assert "strong_wind" in types

    def test_poor_visibility_triggers_watch(self):
        result = check_alerts(make_weather(visibility=100))
        assert result["alert"] is True
        types = [a["type"] for a in result["alerts"]]
        assert "poor_visibility" in types

    def test_disclaimer_always_present(self):
        result = check_alerts(make_weather())
        assert "disclaimer" in result
        assert "IMD" in result["disclaimer"] or "Forecast-derived" in result["disclaimer"]

    def test_forecast_rain_watch(self):
        forecast = [{"rain_3h": 20.0, "pop": 0.9, "condition_id": 500} for _ in range(2)]
        result = check_alerts(make_weather(), forecast)
        assert result["alert"] is True
        types = [a["type"] for a in result["alerts"]]
        assert "forecast_rain" in types
