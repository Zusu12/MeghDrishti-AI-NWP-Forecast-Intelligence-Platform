"""
ml/weighting_engine.py — Adaptive Model Weighting Engine
Computes dynamic, normalized model weights (w_m >= 0, sum(w_m) = 1.0)
conditioned on historical skill, lead time, region, season, weather regime, and availability.
"""
import math
import logging
from typing import Dict, List, Optional, Any
from ml.skill_verification import model_skill_service
from schemas.blending import DynamicWeights

logger = logging.getLogger("ml.weighting_engine")


class AdaptiveWeightEngine:
    """
    Dynamic weighting engine implementing the inverse-error formulation
    with lead-time decay and atmospheric regime modulation.
    """

    def __init__(self):
        # Regime sensitivity multiplier: models with finer physics/mesoscale grid
        # receive boosted score during convective/heavy rain events.
        self._regime_multipliers = {
            "heavy_rainfall": {"WRF": 1.40, "ECMWF": 1.10, "GFS": 0.80},
            "convective": {"WRF": 1.35, "ECMWF": 1.05, "GFS": 0.85},
            "storm_cyclone": {"ECMWF": 1.25, "WRF": 1.20, "GFS": 0.90},
            "heatwave": {"ECMWF": 1.20, "GFS": 1.10, "WRF": 0.95},
            "monsoon": {"ECMWF": 1.15, "WRF": 1.10, "GFS": 0.95},
            "dry_spell": {"ECMWF": 1.10, "GFS": 1.05, "WRF": 0.90},
            "high_wind": {"WRF": 1.20, "ECMWF": 1.15, "GFS": 0.90},
            "normal": {"ECMWF": 1.10, "WRF": 1.00, "GFS": 1.00},
        }

    def compute_weights(
        self,
        available_models: List[str],
        variable: str = "temperature",
        lead_time_hours: int = 24,
        region: str = "coastal_ap",
        season: str = "monsoon",
        weather_regime: str = "normal",
        recent_errors: Optional[Dict[str, float]] = None,
    ) -> DynamicWeights:
        """
        Calculate dynamic normalized weights satisfying w_m >= 0 and sum(w_m) == 1.0.
        """
        if not available_models:
            raise ValueError("Cannot calculate weights with zero available models.")

        # Single model edge case
        if len(available_models) == 1:
            m = available_models[0]
            return DynamicWeights(
                variable=variable,
                lead_time_hours=lead_time_hours,
                weights={m: 1.0},
                weather_regime=weather_regime,
                algorithm="single_model_fallback",
                rationale=f"Only {m} is operational/available.",
            )

        raw_scores: Dict[str, float] = {}
        epsilon = 0.01  # Prevent division by zero

        regime_mults = self._regime_multipliers.get(weather_regime, self._regime_multipliers["normal"])

        for model in available_models:
            # 1. Retrieve historical skill (MAE)
            skill = model_skill_service.get_skill(
                model_name=model,
                region=region,
                season=season,
                variable=variable,
                lead_time_hours=lead_time_hours,
            )
            base_mae = skill.mae if skill else 1.5

            # 2. Ingest recent real-time observational error if provided
            if recent_errors and model in recent_errors:
                effective_error = (0.7 * base_mae) + (0.3 * recent_errors[model])
            else:
                effective_error = base_mae

            # 3. Base inverse-error score: lower error = higher score
            score = 1.0 / (effective_error + epsilon)

            # 4. Lead-time decay penalty: models with faster skill degradation lose weight at long leads
            # GFS maintains synoptic stability at 96-120h; WRF degrades slightly faster after 72h
            if lead_time_hours > 72:
                if model == "GFS":
                    score *= 1.10
                elif model == "WRF":
                    score *= 0.90

            # 5. Apply weather regime modulation
            mult = regime_mults.get(model, 1.0)
            score *= mult

            raw_scores[model] = max(0.001, score)

        # 6. Normalize weights: sum(w_m) = 1.0
        total_score = sum(raw_scores.values())
        normalized_weights: Dict[str, float] = {}

        for model, score in raw_scores.items():
            w = round(score / total_score, 4)
            normalized_weights[model] = w

        # Ensure exact sum to 1.0 by adjusting largest weight for rounding residue
        diff = round(1.0 - sum(normalized_weights.values()), 4)
        if abs(diff) > 0.0:
            top_model = max(normalized_weights, key=normalized_weights.get)
            normalized_weights[top_model] = round(normalized_weights[top_model] + diff, 4)

        rationale = (
            f"Weights conditioned on {weather_regime.upper()} regime, {lead_time_hours}h lead, "
            f"and historical {variable} MAE in {region.replace('_', ' ').title()}."
        )

        return DynamicWeights(
            variable=variable,
            lead_time_hours=lead_time_hours,
            weights=normalized_weights,
            weather_regime=weather_regime,
            algorithm="adaptive_inverse_skill_regime_modulated",
            rationale=rationale,
        )

    def generate_weight_map(
        self,
        variable: str = "temperature",
        lead_time_hours: int = 24,
        season: str = "monsoon",
        weather_regime: str = "normal",
    ) -> List[Dict[str, Any]]:
        """
        Generate spatial model weight distribution across major Indian meteorological subdivisions.
        Used directly by the 'Weight Maps' frontend component.
        """
        regions = [
            {"id": "coastal_ap", "name": "Visakhapatnam (Coastal Andhra Pradesh)", "lat": 17.6868, "lon": 83.2185},
            {"id": "western_ghats", "name": "Mumbai (Konkan & Western Ghats)", "lat": 19.0760, "lon": 72.8777},
            {"id": "north_india", "name": "New Delhi (North-West Plains)", "lat": 28.6139, "lon": 77.2090},
            {"id": "east_india", "name": "Kolkata (Gangetic West Bengal)", "lat": 22.5726, "lon": 88.3639},
            {"id": "south_india", "name": "Bengaluru (South Interior Karnataka)", "lat": 12.9716, "lon": 77.5946},
            {"id": "central_india", "name": "Bhopal (Central India / MP)", "lat": 23.2599, "lon": 77.4126},
            {"id": "northeast_india", "name": "Guwahati (Assam & Meghalaya)", "lat": 26.1445, "lon": 91.7362},
            {"id": "chennai_coast", "name": "Chennai (Coastal Tamil Nadu)", "lat": 13.0827, "lon": 80.2707},
        ]

        results = []
        for reg in regions:
            w_res = self.compute_weights(
                available_models=["GFS", "WRF", "ECMWF"],
                variable=variable,
                lead_time_hours=lead_time_hours,
                region=reg["id"],
                season=season,
                weather_regime=weather_regime,
            )
            top_model = max(w_res.weights, key=w_res.weights.get)
            results.append({
                "region_id": reg["id"],
                "region_name": reg["name"],
                "coordinates": {"lat": reg["lat"], "lon": reg["lon"]},
                "weights": w_res.weights,
                "dominant_model": top_model,
                "dominant_weight_pct": round(w_res.weights[top_model] * 100.0, 1),
                "regime": weather_regime,
                "lead_time_hours": lead_time_hours,
            })

        return results


# Global singleton
weighting_engine = AdaptiveWeightEngine()
