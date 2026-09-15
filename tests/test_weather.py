"""
tests/test_weather.py — Weather service unit tests
"""
import pytest
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from weather_service import resolve_city, CITY_ALIASES, get_current_weather, get_forecast


class TestCityAliases:
    def test_vizag_resolves(self):
        assert resolve_city("vizag") == "Visakhapatnam"

    def test_bombay_resolves(self):
        assert resolve_city("bombay") == "Mumbai"

    def test_madras_resolves(self):
        assert resolve_city("madras") == "Chennai"

    def test_bangalore_resolves(self):
        assert resolve_city("bangalore") == "Bengaluru"

    def test_calcutta_resolves(self):
        assert resolve_city("calcutta") == "Kolkata"

    def test_normal_city_unchanged(self):
        assert resolve_city("Delhi") == "Delhi"

    def test_case_insensitive(self):
        assert resolve_city("VIZAG") == "Visakhapatnam"
        assert resolve_city("  bOmBaY  ") == "Mumbai"


class TestWeatherNormalization:
    def test_demo_weather_structure(self):
        from weather_service import DEMO_WEATHER
        required = [
            "temperature", "feels_like", "humidity", "pressure",
            "wind_speed", "visibility", "condition", "lat", "lon"
        ]
        for key in required:
            assert key in DEMO_WEATHER, f"Missing key: {key}"

    def test_demo_forecast_structure(self):
        from weather_service import DEMO_FORECAST
        assert len(DEMO_FORECAST) > 0
        required = ["dt", "temperature", "feels_like", "humidity", "wind_speed", "condition", "pop"]
        for key in required:
            assert key in DEMO_FORECAST[0], f"Missing forecast key: {key}"


class TestWeatherCoordinates:
    def test_get_current_weather_by_coords(self):
        result = asyncio.run(get_current_weather(lat=17.6868, lon=83.2185))
        assert "temperature" in result
        assert "condition" in result
        assert "lat" in result
        assert "lon" in result

    def test_get_forecast_by_coords(self):
        result = asyncio.run(get_forecast(lat=17.6868, lon=83.2185))
        assert isinstance(result, list)
        assert len(result) > 0
        assert "temperature" in result[0]
        assert "pop" in result[0]
