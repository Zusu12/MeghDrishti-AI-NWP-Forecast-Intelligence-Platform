"""
schemas/verification.py — Historical Model Skill & Verification Schemas
Covers continuous (MAE, RMSE, Bias) and categorical contingency metrics (POD, FAR, CSI).
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ModelSkillRecord(BaseModel):
    """
    Evaluation skill record for an individual NWP model or blended consensus.
    Partitioned across model, region, season, variable, lead time, and regime.
    """
    model_name: str = Field(..., description="Model identifier: GFS | WRF | ECMWF | BLENDED")
    region: str = Field(..., description="Geographic region / meteorological subdivision (e.g., Coastal AP, North-West)")
    season: str = Field(..., description="Climatological season: monsoon | pre_monsoon | post_monsoon | winter")
    variable: str = Field(..., description="Meteorological variable: temperature | precipitation | wind_speed | pressure")
    lead_time_hours: int = Field(..., ge=0, description="Forecast lead time in hours")
    weather_regime: str = Field("all", description="Associated weather regime or 'all'")
    
    # Continuous verification metrics
    mae: float = Field(..., ge=0.0, description="Mean Absolute Error")
    rmse: float = Field(..., ge=0.0, description="Root Mean Square Error")
    bias: float = Field(..., description="Mean Bias Error (positive = over-prediction, negative = under-prediction)")
    
    # Categorical verification metrics (especially for rain events)
    pod: Optional[float] = Field(None, ge=0.0, le=1.0, description="Probability of Detection / Hit Rate")
    far: Optional[float] = Field(None, ge=0.0, le=1.0, description="False Alarm Ratio")
    csi: Optional[float] = Field(None, ge=0.0, le=1.0, description="Critical Success Index / Threat Score")
    
    sample_count: int = Field(..., ge=1, description="Number of verification forecast-observation pairs evaluated")
    evaluation_period: str = Field(..., description="Date range or dataset descriptor for the evaluation")
    is_synthetic: bool = Field(False, description="Flag indicating synthetic baseline data versus real field dataset")


class VerificationComparison(BaseModel):
    """Comparative verification report contrasting individual models against the Blended Consensus."""
    variable: str
    region: str
    lead_time_hours: int
    models: Dict[str, Dict[str, float]]  # e.g., {"GFS": {"mae": 1.8}, "WRF": {"mae": 1.5}, "BLENDED": {"mae": 1.2}}
    improvement_pct: Optional[float] = None
    better_than_all_single_models: bool = False
    verdict: str
