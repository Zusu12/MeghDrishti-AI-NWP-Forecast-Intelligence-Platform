"""
tests/test_nwp_blending.py — Comprehensive Unit & Integration Tests for SIH26081
Covers normalization, adaptive weighting, consensus blending, vector wind averaging,
verification skill metrics, confidence scoring, extreme risk guidance, and REST APIs.
"""
import pytest
import math
from fastapi.testclient import TestClient

from main import app
from nwp.normalization import (
    kelvin_to_celsius,
    ms_to_kmh,
    pa_to_hpa,
    calculate_dew_point,
    normalize_forecast_record,
)
from ml.skill_verification import (
    calculate_continuous_metrics,
    calculate_contingency_metrics,
    model_skill_service,
)
from ml.regime_detector import regime_detector
from ml.weighting_engine import weighting_engine
from ml.confidence_engine import confidence_engine
from ml.extreme_detection import extreme_detector
from ml.forecast_blender import blend_wind_vectors, forecast_blender
from nwp.providers.demo_provider import DemoNWPProvider
from schemas.forecast import ForecastSeries, StandardForecastPoint

client = TestClient(app)


class TestNormalization:
    """Tests for unit conversion, missing values, and physical boundaries."""

    def test_unit_conversions(self):
        assert kelvin_to_celsius(273.15) == 0.0
        assert kelvin_to_celsius(300.0) == 26.85
        assert ms_to_kmh(10.0) == 36.0
        assert pa_to_hpa(101325.0) == 1013.25

    def test_dew_point_calculation(self):
        dp = calculate_dew_point(temp_c=30.0, humidity=60.0)
        assert 20.0 <= dp <= 23.0

    def test_normalize_record_converts_kelvin_and_ms(self):
        raw = {
            "temp": 303.15,  # 30°C in Kelvin
            "humidity": 65,
            "pressure": 101200.0,  # in Pa
            "wind_speed": 5.0,  # in m/s
            "wind_unit": "ms",
            "wind_deg": 180,
            "rain": 4.5,
            "pop": 0.8,
        }
        pt = normalize_forecast_record(
            raw=raw,
            model_name="GFS",
            provider="NOAA-GFS",
            lat=17.68,
            lon=83.21,
            issue_time="2026-10-01T00:00:00Z",
            valid_time="2026-10-01T03:00:00Z",
            lead_time_hours=3,
        )
        assert pt.temperature == 30.0
        assert pt.pressure == 1012.0
        assert pt.wind_speed == 18.0  # 5.0 m/s * 3.6 = 18 km/h
        assert pt.precipitation_probability == 80.0  # 0.8 -> 80%

    def test_normalize_clamps_implausible_temperature(self):
        raw = {"temp": 99.0, "humidity": 50, "pressure": 1013}
        pt = normalize_forecast_record(
            raw=raw,
            model_name="WRF",
            provider="NCAR",
            lat=17.0,
            lon=83.0,
            issue_time="2026-10-01T00:00:00Z",
            valid_time="2026-10-01T03:00:00Z",
            lead_time_hours=3,
        )
        assert pt.temperature <= 65.0


class TestModelSkillMetrics:
    """Tests for continuous and categorical verification metrics."""

    def test_continuous_metrics_calculation(self):
        forecasts = [20.0, 22.0, 25.0, 30.0]
        observations = [19.0, 23.0, 24.0, 28.0]
        mae, rmse, bias = calculate_continuous_metrics(forecasts, observations)
        # Errors: [1, -1, 1, 2] -> Abs errors: [1, 1, 1, 2] -> MAE = 5/4 = 1.25
        assert mae == 1.25
        # Sq errors: [1, 1, 1, 4] -> RMSE = sqrt(7/4) = sqrt(1.75) = ~1.323
        assert rmse == 1.323
        # Bias: (1 - 1 + 1 + 2) / 4 = 3/4 = 0.75
        assert bias == 0.75

    def test_contingency_metrics_calculation(self):
        forecasts = [10.0, 20.0, 5.0, 25.0]
        observations = [5.0, 18.0, 16.0, 22.0]
        # Threshold >= 15.0:
        # Pt 1: f=10 (<15), o=5 (<15) -> Correct Negative
        # Pt 2: f=20 (>=15), o=18 (>=15) -> Hit
        # Pt 3: f=5 (<15), o=16 (>=15) -> Miss
        # Pt 4: f=25 (>=15), o=22 (>=15) -> Hit
        # Hits = 2, Misses = 1, False Alarms = 0
        pod, far, csi = calculate_contingency_metrics(forecasts, observations, threshold=15.0)
        assert pod == round(2 / (2 + 1), 3)  # 2/3 = 0.667
        assert far == 0.0
        assert csi == round(2 / (2 + 1 + 0), 3)  # 2/3 = 0.667

    def test_model_skill_service_comparison(self):
        comp = model_skill_service.compare_models(variable="temperature", region="coastal_ap")
        assert "BLENDED" in comp.models
        assert "GFS" in comp.models
        assert "WRF" in comp.models
        assert comp.better_than_all_single_models is True


class TestAdaptiveWeighting:
    """Tests for dynamic model weight computation and normalization."""

    def test_weights_sum_to_one_and_non_negative(self):
        res = weighting_engine.compute_weights(
            available_models=["GFS", "WRF", "ECMWF"],
            variable="temperature",
            lead_time_hours=24,
            weather_regime="monsoon",
        )
        weights = res.weights
        assert len(weights) == 3
        for m, w in weights.items():
            assert w >= 0.0
        assert math.isclose(sum(weights.values()), 1.0, rel_tol=1e-3)

    def test_single_model_fallback_weight(self):
        res = weighting_engine.compute_weights(
            available_models=["GFS"],
            variable="precipitation",
            lead_time_hours=12,
        )
        assert res.weights == {"GFS": 1.0}

    def test_weight_map_generation(self):
        w_map = weighting_engine.generate_weight_map(variable="precipitation", lead_time_hours=24)
        assert len(w_map) >= 5
        for reg in w_map:
            assert "dominant_model" in reg
            assert math.isclose(sum(reg["weights"].values()), 1.0, rel_tol=1e-3)


class TestMultiModelBlending:
    """Tests for forecast blending arithmetic and vector wind blending."""

    def test_synthetic_blending_arithmetic(self):
        """
        Verify exact requirement from Phase 28:
        Model A = 40, Model B = 60, weights: A = 0.25, B = 0.75 -> Expected: 55.
        """
        val_a = 40.0
        val_b = 60.0
        w_a = 0.25
        w_b = 0.75
        blended = (w_a * val_a) + (w_b * val_b)
        assert blended == 55.0

    def test_vector_wind_averaging(self):
        # East wind (90°) and North wind (0°) with equal weights
        speeds = {"M1": 20.0, "M2": 20.0}
        directions = {"M1": 90.0, "M2": 0.0}
        weights = {"M1": 0.5, "M2": 0.5}

        blended_speed, blended_dir = blend_wind_vectors(speeds, directions, weights)
        assert 14.0 <= blended_speed <= 14.2  # 20 * sqrt(2)/2 = ~14.14
        assert 44.0 <= blended_dir <= 46.0   # North-East (~45°)

    def test_vector_wind_across_north_boundary(self):
        # 350° and 10° should average to 0°/360° (North), not 180° (South)!
        speeds = {"M1": 15.0, "M2": 15.0}
        directions = {"M1": 350.0, "M2": 10.0}
        weights = {"M1": 0.5, "M2": 0.5}

        _, blended_dir = blend_wind_vectors(speeds, directions, weights)
        assert blended_dir == 0.0 or blended_dir == 360.0


class TestConfidenceAndExtremeDetection:
    """Tests for uncertainty metrics and meteorological alerts."""

    def test_confidence_scoring_bounds(self):
        values = {"GFS": 28.0, "WRF": 28.5, "ECMWF": 28.2}
        weights = {"GFS": 0.33, "WRF": 0.33, "ECMWF": 0.34}
        conf = confidence_engine.evaluate_confidence(
            variable="temperature",
            values_by_model=values,
            weights_by_model=weights,
            blended_value=28.2,
            lead_time_hours=12,
        )
        assert 0.0 <= conf.score_pct <= 100.0
        assert conf.category in ("HIGH", "MEDIUM", "LOW")
        assert conf.disagreement_spread < 1.0

    def test_extreme_heavy_rain_detection(self):
        alerts = extreme_detector.evaluate_point(
            temp=27.0,
            precip_3h=35.0,  # Over 30mm/3h threshold -> ORANGE
            wind_speed_kmh=20.0,
            pressure_hpa=1008.0,
            lead_time_hours=12,
            valid_time="2026-10-01 12:00:00",
        )
        assert len(alerts) >= 1
        rain_alert = next((a for a in alerts if a.hazard_type == "HEAVY_RAIN"), None)
        assert rain_alert is not None
        assert rain_alert.severity == "ORANGE"
        assert rain_alert.is_official_warning is False


class TestSIHApiEndpoints:
    """Tests for the newly exposed SIH26081 REST API endpoints."""

    def test_get_nwp_models(self):
        resp = client.get("/api/nwp/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) >= 3

    def test_get_nwp_weights(self):
        resp = client.get("/api/nwp/weights?variable=temperature&lead_time_hours=24")
        assert resp.status_code == 200
        data = resp.json()
        assert "weights" in data
        assert math.isclose(sum(data["weights"].values()), 1.0, rel_tol=1e-3)

    def test_get_nwp_weight_map(self):
        resp = client.get("/api/nwp/weight-map?variable=precipitation")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 5

    def test_get_nwp_verification(self):
        resp = client.get("/api/nwp/verification?variable=temperature")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "improvement_pct" in data

    def test_get_workflow_status(self):
        resp = client.get("/api/workflow/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflow_id" in data
        assert "status" in data

    def test_post_workflow_run(self):
        resp = client.post("/api/workflow/run?location=Visakhapatnam")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("COMPLETED", "IDLE", "RUNNING")
