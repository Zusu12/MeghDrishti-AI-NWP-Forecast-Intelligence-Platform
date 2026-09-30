"""
schemas/forecast.py — Standardized Meteorological Forecast Schemas
Strictly enforces common scientific schema across all NWP models and observations.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class StandardForecastPoint(BaseModel):
    """
    Standardized forecast point schema required for multi-model NWP processing.
    All models (GFS, WRF, ECMWF, Demo) are normalized into this format.
    """
    model_name: str = Field(..., description="Canonical name of the forecast model (e.g., GFS, WRF, ECMWF)")
    provider: str = Field(..., description="Data provider or organization (e.g., NOAA-NCEP, NCAR, ECMWF, OWM)")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    issue_time: str = Field(..., description="Model initialization/run cycle timestamp in ISO-8601 UTC")
    valid_time: str = Field(..., description="Target forecast valid time in ISO-8601 UTC")
    lead_time_hours: int = Field(..., ge=0, description="Forecast lead time in hours from initialization")
    
    # Core meteorological variables (Standardized units)
    temperature: float = Field(..., description="2m Air Temperature in Celsius (°C)")
    precipitation: float = Field(..., ge=0.0, description="Accumulated precipitation over step interval in mm")
    precipitation_probability: float = Field(0.0, ge=0.0, le=100.0, description="Probability of precipitation (0-100%)")
    wind_speed: float = Field(..., ge=0.0, description="10m Wind Speed in km/h")
    wind_direction: float = Field(..., ge=0.0, le=360.0, description="10m Wind Direction in meteorological degrees (0-360°)")
    pressure: float = Field(..., ge=800.0, le=1100.0, description="Surface/Sea-Level atmospheric pressure in hPa")
    humidity: float = Field(..., ge=0.0, le=100.0, description="2m Relative Humidity in percentage (0-100%)")
    
    # Optional atmospheric diagnostics
    dew_point: Optional[float] = Field(None, description="2m Dew Point Temperature in Celsius (°C)")
    cloud_cover: Optional[float] = Field(None, ge=0.0, le=100.0, description="Total Cloud Cover in percentage (0-100%)")
    weather_regime: Optional[str] = Field("normal", description="Detected or associated weather regime")
    
    # Provenance and telemetry
    data_source: str = Field("live_nwp", description="Source classification: live_nwp | demo_simulated | reference_observation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Model resolution, grid coordinate, or cycle metadata")

    @field_validator("temperature")
    @classmethod
    def validate_temp(cls, v: float) -> float:
        if v < -90.0 or v > 65.0:
            raise ValueError(f"Temperature {v}°C is outside physically plausible terrestrial limits (-90°C to +65°C)")
        return round(v, 2)

    @field_validator("wind_direction")
    @classmethod
    def validate_wind_dir(cls, v: float) -> float:
        return round(v % 360.0, 1)


class ForecastSeries(BaseModel):
    """Complete multi-step forecast run for a single location and model."""
    model_name: str
    provider: str
    location_name: str
    latitude: float
    longitude: float
    issue_time: str
    points: List[StandardForecastPoint]
    data_source: str
    is_demo: bool = False
    disclaimer: Optional[str] = None
