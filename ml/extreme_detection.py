"""
ml/extreme_detection.py — Extreme Weather Risk Guidance Engine
Evaluates consensus forecasts against standardized meteorological thresholds.
Explicitly distinguished as 'MODEL-BASED GUIDANCE', never as official government warnings.
"""
import logging
from typing import List, Optional
from schemas.blending import ExtremeWeatherAlert

logger = logging.getLogger("ml.extreme_detection")


class ExtremeWeatherDetector:
    """Evaluates blended consensus forecasts for severe meteorological threshold breaches."""

    @staticmethod
    def evaluate_point(
        temp: float,
        precip_3h: float,
        wind_speed_kmh: float,
        pressure_hpa: float,
        lead_time_hours: int,
        valid_time: str,
        confidence_tier: str = "MEDIUM",
    ) -> List[ExtremeWeatherAlert]:
        """
        Evaluate single timestep values against IMD-aligned meteorological thresholds.
        """
        alerts: List[ExtremeWeatherAlert] = []

        # 1. Extreme Heavy Rainfall (Thresholds based on standard IMD 3-hourly rates)
        if precip_3h >= 50.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="HEAVY_RAIN",
                    severity="RED",
                    trigger_value=precip_3h,
                    threshold_value=50.0,
                    unit="mm/3h",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Extremely heavy rainfall predicted by consensus models. Potential for severe localized inundation and flash flooding.",
                )
            )
        elif precip_3h >= 30.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="HEAVY_RAIN",
                    severity="ORANGE",
                    trigger_value=precip_3h,
                    threshold_value=30.0,
                    unit="mm/3h",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Very heavy rainfall consensus signal. Prepare for localized waterlogging and reduced visibility.",
                )
            )
        elif precip_3h >= 15.6:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="HEAVY_RAIN",
                    severity="YELLOW",
                    trigger_value=precip_3h,
                    threshold_value=15.6,
                    unit="mm/3h",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Heavy rainfall alert signal. Monitor local drainage and travel routes.",
                )
            )

        # 2. Extreme Heatwave Conditions
        if temp >= 45.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="HEATWAVE",
                    severity="RED",
                    trigger_value=temp,
                    threshold_value=45.0,
                    unit="°C",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Severe heatwave conditions forecasted. Extreme thermal stress risk; avoid outdoor exposure during peak daylight hours.",
                )
            )
        elif temp >= 43.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="HEATWAVE",
                    severity="ORANGE",
                    trigger_value=temp,
                    threshold_value=43.0,
                    unit="°C",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Heatwave conditions forecasted. High dehydration risk; ensure adequate hydration and shade.",
                )
            )
        elif temp >= 40.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="HEATWAVE",
                    severity="YELLOW",
                    trigger_value=temp,
                    threshold_value=40.0,
                    unit="°C",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="High temperature advisory signal. Moderate thermal discomfort expected.",
                )
            )

        # 3. Gale / High Wind Guidance
        if wind_speed_kmh >= 85.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="GALE_WIND",
                    severity="RED",
                    trigger_value=wind_speed_kmh,
                    threshold_value=85.0,
                    unit="km/h",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Destructive gale winds predicted by consensus. Risk of uprooted trees and structural damage.",
                )
            )
        elif wind_speed_kmh >= 65.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="GALE_WIND",
                    severity="ORANGE",
                    trigger_value=wind_speed_kmh,
                    threshold_value=65.0,
                    unit="km/h",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Severe squally winds forecasted. Secure loose structures; hazardous marine and high-altitude conditions.",
                )
            )
        elif wind_speed_kmh >= 50.0:
            alerts.append(
                ExtremeWeatherAlert(
                    hazard_type="GALE_WIND",
                    severity="YELLOW",
                    trigger_value=wind_speed_kmh,
                    threshold_value=50.0,
                    unit="km/h",
                    lead_time_hours=lead_time_hours,
                    valid_time=valid_time,
                    confidence_category=confidence_tier,
                    recommendation="Strong wind gusts predicted. Caution for two-wheelers and coastal watercraft.",
                )
            )

        return alerts


# Global singleton
extreme_detector = ExtremeWeatherDetector()
