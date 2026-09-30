"""
ml/confidence_engine.py — Confidence & Model Disagreement Engine
Quantifies forecast uncertainty, inter-model spread (weighted variance),
inter-model range, and computes an explainable confidence score (0-100% / HIGH/MED/LOW).
"""
import math
import logging
from typing import Dict, List, Tuple
from schemas.blending import ConfidenceMetrics

logger = logging.getLogger("ml.confidence_engine")


class ConfidenceEngine:
    """Computes transparent forecast confidence and model disagreement metrics."""

    # Normalization scale thresholds for spread calculation
    SPREAD_SCALES = {
        "temperature": 3.0,   # 3°C standard tolerance
        "precipitation": 8.0,  # 8 mm standard tolerance
        "wind_speed": 12.0,   # 12 km/h standard tolerance
        "pressure": 4.0,      # 4 hPa standard tolerance
        "humidity": 15.0,     # 15% standard tolerance
    }

    def compute_disagreement(
        self,
        values_by_model: Dict[str, float],
        weights_by_model: Dict[str, float],
        blended_value: float,
    ) -> Tuple[float, float]:
        """
        Compute weighted standard deviation (spread) and absolute range across models.
        Returns:
            (spread_sigma, absolute_range)
        """
        if not values_by_model:
            return 0.0, 0.0

        vals = list(values_by_model.values())
        abs_range = round(max(vals) - min(vals), 2)

        # Weighted variance: sum(w_m * (y_m - blended)^2)
        weighted_var = 0.0
        for m, y in values_by_model.items():
            w = weights_by_model.get(m, 1.0 / len(values_by_model))
            weighted_var += w * ((y - blended_value) ** 2)

        spread_sigma = round(math.sqrt(max(0.0, weighted_var)), 2)
        return spread_sigma, abs_range

    def evaluate_confidence(
        self,
        variable: str,
        values_by_model: Dict[str, float],
        weights_by_model: Dict[str, float],
        blended_value: float,
        lead_time_hours: int,
        weather_regime: str = "normal",
        expected_total_models: int = 3,
    ) -> ConfidenceMetrics:
        """
        Compute composite confidence metrics with explainable rationale.
        """
        active_count = len(values_by_model)
        spread, val_range = self.compute_disagreement(values_by_model, weights_by_model, blended_value)

        # 1. Agreement factor (0.0 to 1.0): lower spread = higher agreement
        scale = self.SPREAD_SCALES.get(variable, 5.0)
        agreement = max(0.0, min(1.0, 1.0 - (spread / scale)))

        # 2. Model coverage factor (0.0 to 1.0)
        coverage = min(1.0, active_count / max(1, expected_total_models))

        # 3. Lead-time penalty factor (0.0 to 1.0)
        lead_penalty = min(1.0, lead_time_hours / 120.0)

        # 4. Composite Confidence Score: 0 to 100%
        # Formula: 45% Agreement + 25% Coverage + 20% Baseline Skill - 10% Lead Penalty
        raw_score = (0.45 * agreement) + (0.25 * coverage) + 0.20 - (0.10 * lead_penalty)
        score_pct = round(max(10.0, min(98.0, raw_score * 100.0)), 1)

        # Confidence category
        if score_pct >= 75.0:
            category = "HIGH"
        elif score_pct >= 50.0:
            category = "MEDIUM"
        else:
            category = "LOW"

        # Explainable factors
        factors = []
        factors.append(f"{active_count}/{expected_total_models} NWP models actively contributing to consensus.")
        if agreement >= 0.75:
            factors.append(f"Strong inter-model agreement (spread: {spread}, range: {val_range}).")
        elif agreement >= 0.50:
            factors.append(f"Moderate inter-model spread ({spread}) across predictions.")
        else:
            factors.append(f"High model divergence (spread: {spread}, range: {val_range}); uncertainty elevated.")

        if lead_time_hours <= 24:
            factors.append(f"Short forecast horizon ({lead_time_hours}h lead) enhances reliability.")
        elif lead_time_hours >= 72:
            factors.append(f"Extended lead time ({lead_time_hours}h) naturally decreases synoptic predictability.")

        if weather_regime in ("heavy_rainfall", "storm_cyclone", "convective"):
            factors.append(f"Active '{weather_regime.upper()}' regime introduces non-linear convective variance.")

        return ConfidenceMetrics(
            score_pct=score_pct,
            category=category,
            agreement_score=round(agreement, 3),
            disagreement_spread=spread,
            inter_model_range=val_range,
            active_models_count=active_count,
            factors=factors,
        )


# Global singleton
confidence_engine = ConfidenceEngine()
