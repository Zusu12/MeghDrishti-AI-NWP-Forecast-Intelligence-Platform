"""
nwp/normalization.py — Meteorological Data Normalization & Quality Control
Normalizes disparate model feeds into validated StandardForecastPoint records.
Handles unit conversions, missing variable imputation, and physical boundary checks.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from schemas.forecast import StandardForecastPoint

logger = logging.getLogger("nwp.normalization")


def kelvin_to_celsius(temp_k: float) -> float:
    """Convert absolute temperature in Kelvin to Celsius."""
    return round(temp_k - 273.15, 2)


def ms_to_kmh(speed_ms: float) -> float:
    """Convert velocity from meters/second to kilometers/hour."""
    return round(speed_ms * 3.6, 2)


def pa_to_hpa(pres_pa: float) -> float:
    """Convert pressure from Pascals (N/m²) to hectopascals (hPa / mb)."""
    return round(pres_pa / 100.0, 2)


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    """
    Calculate dew point temperature in °C using the Magnus-Tetens approximation.
    Used when a model does not directly output surface dew point.
    """
    try:
        if humidity <= 0:
            return round(temp_c - 20.0, 1)
        a = 17.27
        b = 237.7
        alpha = ((a * temp_c) / (b + temp_c)) + math.log(max(0.01, humidity) / 100.0)
        return round((b * alpha) / (a - alpha), 1)
    except Exception:
        return round(temp_c - ((100.0 - humidity) / 5.0), 1)


def normalize_forecast_record(
    raw: Dict[str, Any],
    model_name: str,
    provider: str,
    lat: float,
    lon: float,
    issue_time: str,
    valid_time: str,
    lead_time_hours: int,
    data_source: str = "live_nwp",
) -> StandardForecastPoint:
    """
    Quality-control, convert units, impute missing values, and normalize
    an incoming model timestep into StandardForecastPoint.
    """
    # 1. Temperature (°C)
    raw_temp = raw.get("temperature", raw.get("temp", 25.0))
    if raw_temp > 150.0:  # Indicates Kelvin
        temp_c = kelvin_to_celsius(raw_temp)
    else:
        temp_c = float(raw_temp)
    
    # Physical plausibility clamp
    if temp_c < -90.0 or temp_c > 65.0:
        logger.warning(f"[{model_name}] Implausible temperature {temp_c}°C at step {lead_time_hours}h; clamped.")
        temp_c = max(-90.0, min(65.0, temp_c))

    # 2. Relative Humidity (%)
    raw_hum = float(raw.get("humidity", raw.get("rh", 50.0)))
    humidity = round(max(0.0, min(100.0, raw_hum)), 1)

    # 3. Dew Point (°C)
    raw_dp = raw.get("dew_point", raw.get("dewpoint"))
    if raw_dp is not None:
        dew_point = kelvin_to_celsius(float(raw_dp)) if float(raw_dp) > 150.0 else float(raw_dp)
    else:
        dew_point = calculate_dew_point(temp_c, humidity)

    # 4. Atmospheric Pressure (hPa)
    raw_pres = float(raw.get("pressure", raw.get("surface_pressure", 1013.25)))
    if raw_pres > 2000.0:  # Pascals
        pressure = pa_to_hpa(raw_pres)
    else:
        pressure = raw_pres
    if pressure < 800.0 or pressure > 1100.0:
        logger.warning(f"[{model_name}] Out-of-bounds pressure {pressure} hPa; defaulted to 1013.25.")
        pressure = 1013.25

    # 5. Wind Speed (km/h) & Direction (0-360°)
    raw_wind_spd = float(raw.get("wind_speed", raw.get("wind_spd", 10.0)))
    wind_unit = raw.get("wind_unit", "ms" if raw_wind_spd < 45.0 else "kmh")
    if wind_unit == "ms":
        wind_speed = ms_to_kmh(raw_wind_spd)
    else:
        wind_speed = round(raw_wind_spd, 1)
    wind_speed = max(0.0, min(350.0, wind_speed))

    raw_wind_dir = float(raw.get("wind_direction", raw.get("wind_deg", 0.0)))
    wind_direction = round(raw_wind_dir % 360.0, 1)

    # 6. Precipitation (mm) & Probability of Precipitation (PoP %)
    raw_precip = float(raw.get("precipitation", raw.get("rain", raw.get("precip", 0.0))))
    # Check if precipitation is given in meters
    if 0.0 < raw_precip < 0.01 and "precip_unit" in raw and raw["precip_unit"] == "m":
        precipitation = round(raw_precip * 1000.0, 2)
    else:
        precipitation = round(max(0.0, raw_precip), 2)

    raw_pop = float(raw.get("precipitation_probability", raw.get("pop", 0.0)))
    # If given as ratio (0.0 to 1.0), convert to percentage
    if 0.0 < raw_pop <= 1.0:
        pop_pct = round(raw_pop * 100.0, 1)
    else:
        pop_pct = round(max(0.0, min(100.0, raw_pop)), 1)

    # 7. Cloud Cover (%)
    cloud_cover = round(max(0.0, min(100.0, float(raw.get("cloud_cover", raw.get("clouds", 0.0))))), 1)

    return StandardForecastPoint(
        model_name=model_name,
        provider=provider,
        latitude=round(lat, 4),
        longitude=round(lon, 4),
        issue_time=issue_time,
        valid_time=valid_time,
        lead_time_hours=lead_time_hours,
        temperature=temp_c,
        dew_point=dew_point,
        humidity=humidity,
        pressure=pressure,
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        precipitation=precipitation,
        precipitation_probability=pop_pct,
        cloud_cover=cloud_cover,
        weather_regime=raw.get("weather_regime", "normal"),
        data_source=data_source,
        metadata=raw.get("metadata", {}),
    )
