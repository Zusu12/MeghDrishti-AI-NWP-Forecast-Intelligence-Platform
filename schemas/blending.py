"""
schemas/blending.py — Forecast Blending, Adaptive Weights, and Uncertainty Schemas
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class DynamicWeights(BaseModel):
    """Dynamic model weights for a given variable, lead time, and atmospheric situation."""
    variable: str
    lead_time_hours: int
    weights: Dict[str, float] = Field(..., description="Mapping of model_name -> normalized weight (0.0 to 1.0)")
    weather_regime: str = "normal"
    algorithm: str = "adaptive_inverse_skill"
    rationale: Optional[str] = None

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, weights: Dict[str, float]) -> Dict[str, float]:
        if not weights:
            raise ValueError("Weights mapping cannot be empty")
        for m, w in weights.items():
            if w < 0.0:
                raise ValueError(f"Model weight for {m} cannot be negative: {w}")
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Model weights must sum to 1.0, got {total}")
        return weights


class ConfidenceMetrics(BaseModel):
    """Forecast confidence, model agreement, and spread metrics."""
    score_pct: float = Field(..., ge=0.0, le=100.0, description="Overall confidence score (0-100%)")
    category: str = Field(..., description="Confidence tier: HIGH | MEDIUM | LOW")
    agreement_score: float = Field(..., ge=0.0, le=1.0, description="Inter-model agreement factor (0.0 to 1.0)")
    disagreement_spread: float = Field(..., ge=0.0, description="Weighted standard deviation across models")
    inter_model_range: float = Field(..., ge=0.0, description="Absolute difference between max and min model predictions")
    active_models_count: int = Field(..., ge=1, description="Number of models contributing to the consensus")
    factors: List[str] = Field(default_factory=list, description="Explanatory reasons for the confidence rating")


class ExtremeWeatherAlert(BaseModel):
    """Model-based extreme weather risk guidance."""
    hazard_type: str = Field(..., description="HEAVY_RAIN | HEATWAVE | GALE_WIND | CONVECTIVE_STORM")
    severity: str = Field(..., description="YELLOW | ORANGE | RED | NONE")
    trigger_value: float = Field(..., description="Forecasted value triggering the threshold")
    threshold_value: float = Field(..., description="Reference threshold breached")
    unit: str
    lead_time_hours: int
    valid_time: str
    confidence_category: str
    recommendation: str
    is_official_warning: bool = False
    disclaimer: str = (
        "MODEL-BASED RISK GUIDANCE — Generated algorithmically by multi-model NWP consensus. "
        "Not an official government warning. Refer to IMD/NDMA for statutory alerts."
    )


class BlendedForecastPoint(BaseModel):
    """Complete blended consensus point at a specific lead time."""
    valid_time: str
    lead_time_hours: int
    dt: int
    
    # Blended consensus values
    temperature: float
    precipitation: float
    precipitation_probability: float
    wind_speed: float
    wind_direction: float
    pressure: float
    humidity: float
    
    # Model inputs & weights breakdown
    individual_models: Dict[str, Dict[str, float]]
    model_weights: Dict[str, float]
    
    # Uncertainty & Guidance
    confidence: ConfidenceMetrics
    extreme_alerts: List[ExtremeWeatherAlert] = Field(default_factory=list)
    weather_regime: str = "normal"
    data_source: str = "hybrid_blended_nwp"


class BlendedForecastResponse(BaseModel):
    """Full operational blended forecast response across a 120-hour forecast horizon."""
    location: str
    latitude: float
    longitude: float
    cycle_time: str
    timesteps_count: int
    forecast_points: List[BlendedForecastPoint]
    active_models: List[str]
    detected_regime: str
    overall_confidence: str
    extreme_risk_summary: List[str]
    disclaimer: str
