"""
ml/regime_detector.py — Meteorological Weather Regime Detection Engine
Classifies the atmospheric state into distinct regimes that modulate model weighting.
Implements an interpretable physical rule engine with an extension hook for ML classifiers.
"""
from typing import Dict, List, Optional, Any
from schemas.forecast import StandardForecastPoint


class WeatherRegimeDetector:
    """Detects synoptic and mesoscale weather regimes from meteorological parameters."""

    @staticmethod
    def detect_regime_from_point(point: StandardForecastPoint) -> str:
        """Classify single forecast point into a weather regime."""
        # 1. Storm / Cyclone: Low pressure core with gale wind and heavy rain
        if point.pressure < 995.0 and point.wind_speed >= 50.0 and point.precipitation > 5.0:
            return "storm_cyclone"

        # 2. Extreme Heavy Rainfall
        if point.precipitation >= 15.6:  # IMD Heavy Rain rate > 15.6mm/3hr (~65mm/day)
            return "heavy_rainfall"

        # 3. Severe Heatwave
        if point.temperature >= 40.0:
            return "heatwave"

        # 4. Gale / High Wind
        if point.wind_speed >= 50.0:
            return "high_wind"

        # 5. Convective Instability: High heat + high humidity + moderate rain
        if point.temperature >= 32.0 and point.humidity >= 70.0 and point.precipitation > 2.0:
            return "convective"

        # 6. Monsoon Synoptic Flow: Sustained high moisture + southwesterly/northeasterly winds
        if point.humidity >= 75.0 and (point.cloud_cover or 0.0) >= 60.0:
            return "monsoon"

        # 7. Dry Spell
        if point.humidity <= 35.0 and point.precipitation == 0.0:
            return "dry_spell"

        return "normal"

    @classmethod
    def detect_series_regime(cls, points: List[StandardForecastPoint]) -> str:
        """
        Detect dominant or highest-impact weather regime across a multi-step forecast series.
        Prioritizes severe weather states (storm > heavy rain > heatwave > convective > monsoon).
        """
        if not points:
            return "normal"

        regimes = [cls.detect_regime_from_point(p) for p in points]

        priority_order = [
            "storm_cyclone",
            "heavy_rainfall",
            "heatwave",
            "high_wind",
            "convective",
            "monsoon",
            "dry_spell",
            "normal",
        ]

        for prio in priority_order:
            if prio in regimes:
                return prio

        return "normal"


# Global singleton
regime_detector = WeatherRegimeDetector()
