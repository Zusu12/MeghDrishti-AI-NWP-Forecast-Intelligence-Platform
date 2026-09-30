"""
ml/forecast_blender.py — Multi-Model Consensus Forecast Blending Engine
Blends heterogeneous NWP forecasts into an optimal consensus using dynamic weights.
Implements vector wind averaging (orthogonal U/V components), scalar weighted averaging,
uncertainty evaluation, and extreme weather risk detection.
"""
import math
import logging
from typing import Dict, List, Optional
from ml.weighting_engine import weighting_engine
from ml.confidence_engine import confidence_engine
from ml.extreme_detection import extreme_detector
from ml.regime_detector import regime_detector
from schemas.forecast import ForecastSeries, StandardForecastPoint
from schemas.blending import (
    BlendedForecastPoint,
    BlendedForecastResponse,
    ConfidenceMetrics,
)

logger = logging.getLogger("ml.forecast_blender")


def blend_wind_vectors(
    wind_speeds: Dict[str, float],
    wind_directions: Dict[str, float],
    weights: Dict[str, float],
) -> tuple[float, float]:
    """
    Consensus wind blending via polar decomposition into orthogonal U (zonal) and V (meridional) vectors.
    Strictly avoids naive linear degree averaging which errors near 0°/360° north.
    Returns:
        (blended_speed_kmh, blended_direction_deg)
    """
    u_sum = 0.0
    v_sum = 0.0

    for model, speed in wind_speeds.items():
        deg = wind_directions.get(model, 0.0)
        w = weights.get(model, 1.0 / len(wind_speeds))

        rad = math.radians(deg)
        # Meteorological convention: direction wind is blowing FROM
        u = -speed * math.sin(rad)
        v = -speed * math.cos(rad)

        u_sum += w * u
        v_sum += w * v

    blended_speed = round(math.sqrt(u_sum ** 2 + v_sum ** 2), 1)

    if blended_speed < 0.1:
        blended_deg = 0.0
    else:
        rad_blended = math.atan2(-u_sum, -v_sum)
        deg_blended = math.degrees(rad_blended)
        blended_deg = round(deg_blended % 360.0, 1)

    return blended_speed, blended_deg


class MultiModelForecastBlender:
    """Core consensus blending engine for SIH26081."""

    def blend_forecasts(
        self,
        series_by_model: Dict[str, ForecastSeries],
        region: str = "coastal_ap",
        season: str = "monsoon",
    ) -> BlendedForecastResponse:
        """
        Synthesize multi-model forecast series into unified BlendedForecastResponse.
        """
        if not series_by_model:
            raise ValueError("Cannot blend empty model series collection.")

        first_series = next(iter(series_by_model.values()))
        location_name = first_series.location_name
        lat = first_series.latitude
        lon = first_series.longitude
        issue_time = first_series.issue_time
        available_models = list(series_by_model.keys())

        # Determine overall series weather regime
        sample_points = []
        for s in series_by_model.values():
            sample_points.extend(s.points[:8])
        series_regime = regime_detector.detect_series_regime(sample_points)

        blended_points: List[BlendedForecastPoint] = []
        timesteps_count = min(len(s.points) for s in series_by_model.values())

        overall_risks: List[str] = []

        for i in range(timesteps_count):
            step_points: Dict[str, StandardForecastPoint] = {}
            for m, s in series_by_model.items():
                if i < len(s.points):
                    step_points[m] = s.points[i]

            first_pt = next(iter(step_points.values()))
            lead_hours = first_pt.lead_time_hours
            valid_time = first_pt.valid_time
            dt_ts = int(i * 10800)  # 3h timestamp offset

            # Step-level regime
            step_regime = regime_detector.detect_regime_from_point(first_pt)

            # Compute dynamic weights
            temp_weights = weighting_engine.compute_weights(
                available_models=available_models,
                variable="temperature",
                lead_time_hours=lead_hours,
                region=region,
                season=season,
                weather_regime=step_regime,
            ).weights

            rain_weights = weighting_engine.compute_weights(
                available_models=available_models,
                variable="precipitation",
                lead_time_hours=lead_hours,
                region=region,
                season=season,
                weather_regime=step_regime,
            ).weights

            wind_weights = weighting_engine.compute_weights(
                available_models=available_models,
                variable="wind_speed",
                lead_time_hours=lead_hours,
                region=region,
                season=season,
                weather_regime=step_regime,
            ).weights

            # Extract model values
            temps = {m: pt.temperature for m, pt in step_points.items()}
            rains = {m: pt.precipitation for m, pt in step_points.items()}
            pops = {m: pt.precipitation_probability for m, pt in step_points.items()}
            pressures = {m: pt.pressure for m, pt in step_points.items()}
            humidities = {m: pt.humidity for m, pt in step_points.items()}
            wind_spds = {m: pt.wind_speed for m, pt in step_points.items()}
            wind_dirs = {m: pt.wind_direction for m, pt in step_points.items()}

            # 1. Scalar Blending: sum(w_m * Y_m)
            blended_temp = round(sum(temp_weights[m] * temps[m] for m in available_models), 1)
            blended_rain = round(sum(rain_weights[m] * rains[m] for m in available_models), 2)
            blended_pop = round(sum(rain_weights[m] * pops[m] for m in available_models), 1)
            blended_pres = round(sum(temp_weights[m] * pressures[m] for m in available_models), 1)
            blended_hum = round(sum(temp_weights[m] * humidities[m] for m in available_models), 1)

            # 2. Wind Vector Blending
            blended_ws, blended_wd = blend_wind_vectors(wind_spds, wind_dirs, wind_weights)

            # 3. Confidence & Disagreement Evaluation
            conf = confidence_engine.evaluate_confidence(
                variable="temperature",
                values_by_model=temps,
                weights_by_model=temp_weights,
                blended_value=blended_temp,
                lead_time_hours=lead_hours,
                weather_regime=step_regime,
                expected_total_models=3,
            )

            # 4. Extreme Weather Risk Detection
            alerts = extreme_detector.evaluate_point(
                temp=blended_temp,
                precip_3h=blended_rain,
                wind_speed_kmh=blended_ws,
                pressure_hpa=blended_pres,
                lead_time_hours=lead_hours,
                valid_time=valid_time,
                confidence_tier=conf.category,
            )
            for a in alerts:
                risk_msg = f"{a.severity} Alert ({a.hazard_type}) at {a.valid_time}: {a.trigger_value} {a.unit}"
                if risk_msg not in overall_risks:
                    overall_risks.append(risk_msg)

            # Model inputs breakdown for verification
            individual_inputs = {
                m: {
                    "temperature": temps[m],
                    "precipitation": rains[m],
                    "wind_speed": wind_spds[m],
                    "wind_direction": wind_dirs[m],
                    "pressure": pressures[m],
                    "humidity": humidities[m],
                }
                for m in available_models
            }

            blended_pt = BlendedForecastPoint(
                valid_time=valid_time,
                lead_time_hours=lead_hours,
                dt=dt_ts,
                temperature=blended_temp,
                precipitation=blended_rain,
                precipitation_probability=blended_pop,
                wind_speed=blended_ws,
                wind_direction=blended_wd,
                pressure=blended_pres,
                humidity=blended_hum,
                individual_models=individual_inputs,
                model_weights=temp_weights,
                confidence=conf,
                extreme_alerts=alerts,
                weather_regime=step_regime,
                data_source="hybrid_blended_nwp",
            )
            blended_points.append(blended_pt)

        # High-level confidence rating across first 24h
        first_day_confs = [p.confidence.score_pct for p in blended_points[:8]]
        avg_conf_score = sum(first_day_confs) / len(first_day_confs) if first_day_confs else 70.0
        overall_conf = "HIGH" if avg_conf_score >= 75.0 else ("MEDIUM" if avg_conf_score >= 50.0 else "LOW")

        return BlendedForecastResponse(
            location=location_name,
            latitude=lat,
            longitude=lon,
            cycle_time=issue_time,
            timesteps_count=len(blended_points),
            forecast_points=blended_points,
            active_models=available_models,
            detected_regime=series_regime,
            overall_confidence=overall_conf,
            extreme_risk_summary=overall_risks[:5],
            disclaimer=(
                "HYBRID AI-NWP BLENDED FORECAST — Dynamic multi-model consensus combining GFS, WRF, and ECMWF. "
                "Confidence metrics and model weights generated adaptively."
            ),
        )


# Global singleton
forecast_blender = MultiModelForecastBlender()
