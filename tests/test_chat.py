"""
tests/test_chat.py — FastAPI chat endpoint and API integration tests
Uses TestClient with demo mode / mocking.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["GEMINI_API_KEY"] = ""
os.environ["OPENWEATHERMAP_API_KEY"] = ""
os.environ["ELEVENLABS_API_KEY"] = ""

import config
config.DEMO_MODE = True
config.GEMINI_API_KEY = ""
config.OWM_API_KEY = ""
config.ELEVENLABS_API_KEY = ""

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import config
    config.DEMO_MODE = True
    config.GEMINI_API_KEY = ""
    config.OWM_API_KEY = ""
    config.ELEVENLABS_API_KEY = ""
    from main import app
    import asyncio
    import database
    asyncio.run(database.init_db())
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "apis" in data

    def test_health_shows_demo_mode(self, client):
        res = client.get("/health")
        data = res.json()
        assert data["apis"]["demo_mode"] is True


class TestChat:
    def test_basic_chat_demo_mode(self, client):
        res = client.post("/chat", json={"message": "What is the weather in Delhi?", "language": "en"})
        assert res.status_code == 200
        data = res.json()
        assert "response" in data
        assert data["demo_mode"] is True

    def test_chat_empty_message_rejected(self, client):
        res = client.post("/chat", json={"message": "", "language": "en"})
        assert res.status_code == 422

    def test_chat_message_too_long_rejected(self, client):
        res = client.post("/chat", json={"message": "x" * 1001, "language": "en"})
        assert res.status_code == 422

    def test_chat_invalid_language_rejected(self, client):
        res = client.post("/chat", json={"message": "Weather?", "language": "fr"})
        assert res.status_code == 422

    def test_chat_hindi(self, client):
        res = client.post("/chat", json={"message": "कल मुंबई में मौसम कैसा होगा?", "language": "hi"})
        assert res.status_code == 200
        data = res.json()
        assert "response" in data

    def test_chat_telugu(self, client):
        res = client.post("/chat", json={"message": "రేపు వర్షం పడుతుందా?", "language": "te"})
        assert res.status_code == 200
        data = res.json()
        assert "response" in data

    def test_chat_with_coords(self, client):
        res = client.post("/chat", json={"message": "Weather near me", "language": "en", "lat": 17.6868, "lon": 83.2185})
        assert res.status_code == 200
        data = res.json()
        assert "weather" in data


class TestWeatherEndpoints:
    def test_current_weather_demo(self, client):
        res = client.get("/weather/current?location=Visakhapatnam")
        assert res.status_code == 200
        data = res.json()
        assert "temperature" in data
        assert "humidity" in data

    def test_current_weather_by_coords(self, client):
        res = client.get("/weather/current?lat=17.6868&lon=83.2185")
        assert res.status_code == 200
        data = res.json()
        assert "temperature" in data

    def test_forecast_demo(self, client):
        res = client.get("/weather/forecast?location=Delhi")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_alerts_demo(self, client):
        res = client.get("/alerts?location=Chennai")
        assert res.status_code == 200
        data = res.json()
        assert "alert" in data
        assert "severity" in data
        assert "disclaimer" in data

    def test_climate(self, client):
        res = client.get("/climate?location=Mumbai&days=30")
        assert res.status_code == 200
        data = res.json()
        assert "temperature" in data
        assert "rainfall" in data
        assert data["demo"] is True

    def test_location_search(self, client):
        res = client.get("/location?q=Visakhapatnam")
        assert res.status_code == 200
        data = res.json()
        assert "location" in data


class TestAdvisoryEndpoints:
    @pytest.mark.parametrize("mode", ["agriculture", "aviation", "marine", "travel", "outdoor", "urban"])
    def test_advisory_modes(self, client, mode):
        res = client.post("/advisory", json={"location": "Visakhapatnam", "mode": mode, "language": "en"})
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == mode
        assert "advisory" in data
        assert "disclaimer" in data


class TestNWPEndpoints:
    def test_nwp_forecast(self, client):
        res = client.get("/nwp?location=Visakhapatnam&provider=gfs")
        assert res.status_code == 200
        data = res.json()
        assert "provider" in data
        assert "disclaimer" in data

    def test_nwp_status(self, client):
        res = client.get("/nwp/status")
        assert res.status_code == 200
        data = res.json()
        assert "current_operational" in data
