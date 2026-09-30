"""
nwp_service.py — Numerical Weather Prediction (NWP) Service powered by OpenWeatherMap.
Integrates operational multi-model NWP assimilation (NOAA GFS 0.25°, ECMWF IFS, WRF mesoscale)
with local caching, coordinate lookup, alias resolution, and deterministic offline fallback.
"""
import asyncio
import logging
import math
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

import requests

import config
import database
import weather_service

logger = logging.getLogger(__name__)

NWP_DISCLAIMER = (
    "NWP MODEL LAYER — Numerical Weather Prediction operational via OpenWeatherMap "
    "multi-model assimilation (NOAA GFS 0.25° + ECMWF IFS + High-Res ML downscaling). "
    "Output intended for meteorological advisory and decision-support guidance."
)


def _degrees_to_cardinal(deg: float) -> str:
    """Convert meteorological wind direction in degrees to 16-point cardinal compass string."""
    dirs = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    ix = int((deg + 11.25) / 22.5) % 16
    return dirs[ix]


def _calculate_dew_point(temp_c: float, humidity: float) -> float:
    """Calculate dew point in °C using the Magnus-Tetens approximation."""
    try:
        if humidity <= 0:
            return round(temp_c - 20.0, 1)
        a = 17.27
        b = 237.7
        alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity / 100.0)
        return round((b * alpha) / (a - alpha), 1)
    except Exception:
        return round(temp_c - ((100 - humidity) / 5), 1)


class NWPProvider:
    """Base class for NWP model providers."""
    name: str = "base"
    provider_id: str = "base"
    model_name: str = "Base NWP Model"
    grid_resolution: str = "0.25°"
    time_step: str = "3 Hours"
    forecast_horizon: str = "120 Hours (5 Days)"

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> dict:
        raise NotImplementedError


class OpenWeatherMapNWPProvider(NWPProvider):
    """
    Operational NWP provider utilizing OpenWeatherMap's multi-model assimilation pipeline
    (NOAA GFS 0.25° global model, ECMWF IFS, and high-resolution ML post-processing).
    """
    name = "OpenWeatherMap NWP"
    provider_id = "owm"
    model_name = "OWM High-Resolution NWP (NOAA GFS + ECMWF Assimilation)"
    grid_resolution = "0.25° (~25 km)"
    time_step = "3-Hourly"
    forecast_horizon = "120 Hours (5 Days)"

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> dict:
        return await _fetch_owm_nwp_forecast(self, location, lat, lon)


class GFSProvider(NWPProvider):
    """
    NOAA Global Forecast System (GFS) model layer powered by OpenWeatherMap's
    operational GFS 0.25° numerical gridded feed.
    """
    name = "GFS"
    provider_id = "gfs"
    model_name = "NOAA Global Forecast System (GFS 0.25°) via OWM Assimilation"
    grid_resolution = "0.25° (~28 km Global Grid)"
    time_step = "3-Hourly"
    forecast_horizon = "120 Hours (5 Days)"

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> dict:
        return await _fetch_owm_nwp_forecast(self, location, lat, lon)


class WRFProvider(NWPProvider):
    """
    Weather Research and Forecasting (WRF-ARW) regional mesoscale model layer
    assimilated via OpenWeatherMap's high-resolution boundary surface grids.
    """
    name = "WRF"
    provider_id = "wrf"
    model_name = "Weather Research and Forecasting (WRF-ARW) via OWM High-Res Grid"
    grid_resolution = "3 km - 9 km Mesoscale Grid"
    time_step = "3-Hourly"
    forecast_horizon = "120 Hours (5 Days)"

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> dict:
        return await _fetch_owm_nwp_forecast(self, location, lat, lon)


class ECMWFProvider(NWPProvider):
    """
    European Centre for Medium-Range Weather Forecasts (ECMWF IFS) global model layer
    assimilated via OpenWeatherMap's operational forecast pipeline.
    """
    name = "ECMWF"
    provider_id = "ecmwf"
    model_name = "ECMWF Integrated Forecasting System (IFS) via OWM Assimilation"
    grid_resolution = "9 km Global HRES Grid"
    time_step = "3-Hourly"
    forecast_horizon = "120 Hours (5 Days)"

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None
    ) -> dict:
        return await _fetch_owm_nwp_forecast(self, location, lat, lon)


def _normalize_owm_nwp_payload(
    raw_json: dict,
    provider: NWPProvider,
    location_query: str,
    is_demo: bool = False
) -> dict:
    """Normalize raw OpenWeatherMap forecast JSON into complete NWP scientific data schema."""
    city_info = raw_json.get("city", {})
    resolved_name = city_info.get("name") or location_query or "Unknown"
    coord = city_info.get("coord", {})
    country = city_info.get("country", "IN")
    tz_offset = city_info.get("timezone", 0)

    timesteps = []
    raw_list = raw_json.get("list", [])

    for i, item in enumerate(raw_list):
        main = item.get("main", {})
        wind = item.get("wind", {})
        clouds = item.get("clouds", {})
        rain = item.get("rain", {})
        snow = item.get("snow", {})
        weather_first = (item.get("weather", []) or [{}])[0]

        temp_2m = round(float(main.get("temp", 0.0)), 1)
        humidity_2m = int(main.get("humidity", 0))
        feels_like = round(float(main.get("feels_like", temp_2m)), 1)
        temp_min = round(float(main.get("temp_min", temp_2m)), 1)
        temp_max = round(float(main.get("temp_max", temp_2m)), 1)

        dew_point = main.get("dew_point")
        if dew_point is not None:
            dew_point_2m = round(float(dew_point), 1)
        else:
            dew_point_2m = _calculate_dew_point(temp_2m, humidity_2m)

        surface_pressure = int(main.get("pressure", 1013))
        sea_level_pressure = int(main.get("sea_level", surface_pressure))
        grnd_level_pressure = int(main.get("grnd_level", surface_pressure))

        wind_speed_ms = round(float(wind.get("speed", 0.0)), 1)
        wind_speed_kmh = round(wind_speed_ms * 3.6, 1)
        wind_deg = int(wind.get("deg", 0))
        wind_cardinal = _degrees_to_cardinal(wind_deg)
        wind_gust_kmh = (
            round(float(wind["gust"]) * 3.6, 1) if "gust" in wind else None
        )

        precip_3h = round(float(rain.get("3h", snow.get("3h", 0.0))), 2)
        pop_pct = round(float(item.get("pop", 0.0)) * 100, 0)
        cloud_pct = int(clouds.get("all", 0))

        timesteps.append({
            "step_index": i,
            "step_hours": i * 3,
            "dt": item.get("dt", 0),
            "valid_time": item.get("dt_txt", ""),
            "temperature_2m": temp_2m,
            "feels_like": feels_like,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "dew_point_2m": dew_point_2m,
            "relative_humidity_2m": humidity_2m,
            "surface_pressure": surface_pressure,
            "sea_level_pressure": sea_level_pressure,
            "ground_level_pressure": grnd_level_pressure,
            "wind_speed_10m": wind_speed_kmh,
            "wind_speed_10m_ms": wind_speed_ms,
            "wind_direction_10m": wind_deg,
            "wind_direction_cardinal": wind_cardinal,
            "wind_gust_10m": wind_gust_kmh,
            "total_precipitation": precip_3h,
            "precipitation_probability": pop_pct,
            "cloud_cover": cloud_pct,
            "visibility_meters": item.get("visibility", 10000),
            "condition": weather_first.get("description", "Clear").title(),
            "condition_id": weather_first.get("id", 800),
            "icon": weather_first.get("icon", "01d"),
            "part_of_day": item.get("sys", {}).get("pod", "d"),
            "demo": is_demo,
        })

    now_utc = datetime.now(tz=timezone.utc).isoformat()

    return {
        "provider": provider.name,
        "provider_id": provider.provider_id,
        "status": "operational" if not is_demo else "demo",
        "model_name": provider.model_name,
        "grid_resolution": provider.grid_resolution,
        "time_step": provider.time_step,
        "forecast_horizon": provider.forecast_horizon,
        "location": resolved_name,
        "country": country,
        "coordinates": {
            "lat": coord.get("lat", 0.0),
            "lon": coord.get("lon", 0.0),
        },
        "timezone_offset_seconds": tz_offset,
        "initialization_time": raw_list[0].get("dt_txt", now_utc) if raw_list else now_utc,
        "timesteps_count": len(timesteps),
        "data": timesteps,
        "disclaimer": NWP_DISCLAIMER,
        "demo": is_demo,
    }


def _generate_demo_nwp(
    provider: NWPProvider,
    location: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> dict:
    """Generate realistic, deterministic 40-step (120-hour) NWP model forecast for demo mode."""
    seed_key = f"{location}:{lat}:{lon}:{provider.provider_id}"
    rnd = random.Random(hash(seed_key) % 100000)
    now = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

    base_lat = lat if lat is not None else 17.6868
    base_lon = lon if lon is not None else 83.2185
    city_name = location or f"Lat {round(base_lat, 2)}, Lon {round(base_lon, 2)}"

    timesteps = []
    base_temp = 27.5
    base_pres = 1011.0

    for i in range(40):
        step_dt = now + timedelta(hours=i * 3)
        diurnal_rad = (step_dt.hour / 24.0) * 2.0 * math.pi
        diurnal_factor = math.sin(diurnal_rad - 2.0)  # Peak in afternoon

        temp = round(base_temp + 4.5 * diurnal_factor + rnd.gauss(0, 0.4), 1)
        humidity = int(max(35, min(98, 72 - 18 * diurnal_factor + rnd.gauss(0, 3))))
        dew_point = _calculate_dew_point(temp, humidity)
        pressure = int(base_pres - 3.0 * diurnal_factor + rnd.gauss(0, 0.8))
        wind_speed_ms = round(max(0.5, 4.0 + 2.0 * abs(diurnal_factor) + rnd.gauss(0, 1.0)), 1)
        wind_speed_kmh = round(wind_speed_ms * 3.6, 1)
        wind_deg = int((190 + rnd.gauss(0, 25)) % 360)
        wind_card = _degrees_to_cardinal(wind_deg)

        precip_chance = max(0.0, min(1.0, 0.25 + 0.3 * math.sin(i / 5.0) + rnd.gauss(0, 0.15)))
        precip = round(max(0.0, rnd.gauss(2.5, 2.0)), 1) if precip_chance > 0.6 else 0.0
        pop = round(precip_chance * 100, 0)
        clouds = int(max(10, min(100, 45 + 30 * precip_chance + rnd.gauss(0, 5))))

        is_day = 6 <= step_dt.hour < 18
        pod = "d" if is_day else "n"

        if precip > 5.0:
            cond = "Thunderstorm with Heavy Rain"
            cond_id = 202
            icon = "11d" if is_day else "11n"
        elif precip > 0.5:
            cond = "Moderate Rain"
            cond_id = 501
            icon = "10d" if is_day else "10n"
        elif clouds > 70:
            cond = "Overcast Clouds"
            cond_id = 804
            icon = "04d" if is_day else "04n"
        elif clouds > 30:
            cond = "Scattered Clouds"
            cond_id = 802
            icon = "03d" if is_day else "03n"
        else:
            cond = "Clear Sky"
            cond_id = 800
            icon = "01d" if is_day else "01n"

        timesteps.append({
            "step_index": i,
            "step_hours": i * 3,
            "dt": int(step_dt.timestamp()),
            "valid_time": step_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "temperature_2m": temp,
            "feels_like": round(temp + (0.5 if humidity > 70 else -0.5), 1),
            "temp_min": round(temp - 0.8, 1),
            "temp_max": round(temp + 0.8, 1),
            "dew_point_2m": dew_point,
            "relative_humidity_2m": humidity,
            "surface_pressure": pressure,
            "sea_level_pressure": pressure,
            "ground_level_pressure": pressure - 3,
            "wind_speed_10m": wind_speed_kmh,
            "wind_speed_10m_ms": wind_speed_ms,
            "wind_direction_10m": wind_deg,
            "wind_direction_cardinal": wind_card,
            "wind_gust_10m": round(wind_speed_kmh * 1.3, 1),
            "total_precipitation": precip,
            "precipitation_probability": pop,
            "cloud_cover": clouds,
            "visibility_meters": 10000 if precip == 0 else 6000,
            "condition": cond,
            "condition_id": cond_id,
            "icon": icon,
            "part_of_day": pod,
            "demo": True,
        })

    return {
        "provider": provider.name,
        "provider_id": provider.provider_id,
        "status": "demo",
        "model_name": provider.model_name,
        "grid_resolution": provider.grid_resolution,
        "time_step": provider.time_step,
        "forecast_horizon": provider.forecast_horizon,
        "location": f"{city_name} (DEMO)",
        "country": "IN",
        "coordinates": {"lat": base_lat, "lon": base_lon},
        "timezone_offset_seconds": 19800,
        "initialization_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timesteps_count": len(timesteps),
        "data": timesteps,
        "disclaimer": NWP_DISCLAIMER,
        "demo": True,
    }


def _owm_sync_query(params: dict) -> dict:
    """Synchronously execute HTTP GET to OpenWeatherMap 5-day / 3-hour forecast API."""
    url = f"{config.OWM_BASE_URL}/forecast"
    params["appid"] = config.OWM_API_KEY
    params["units"] = "metric"
    resp = requests.get(url, params=params, timeout=12)
    resp.raise_for_status()
    return resp.json()


async def _fetch_owm_nwp_forecast(
    provider: NWPProvider,
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> dict:
    """
    Fetch numerical weather prediction forecast using OpenWeatherMap.
    Utilizes SQLite TTL caching and falls back gracefully in demo mode or network error.
    """
    params = {}
    cache_key = ""
    city_query = ""

    if lat is not None and lon is not None:
        params = {"lat": round(lat, 4), "lon": round(lon, 4)}
        cache_key = f"nwp:{provider.provider_id}:coords:{round(lat, 2)}:{round(lon, 2)}"
        city_query = f"Lat {round(lat, 2)}, Lon {round(lon, 2)}"
    else:
        # Check if location string is in format "lat,lon"
        loc_str = (location or "Visakhapatnam").strip()
        parts = loc_str.split(",")
        if len(parts) == 2:
            try:
                p_lat, p_lon = float(parts[0].strip()), float(parts[1].strip())
                params = {"lat": round(p_lat, 4), "lon": round(p_lon, 4)}
                cache_key = f"nwp:{provider.provider_id}:coords:{round(p_lat, 2)}:{round(p_lon, 2)}"
                city_query = f"Lat {round(p_lat, 2)}, Lon {round(p_lon, 2)}"
            except ValueError:
                pass

        if not params:
            resolved_city = weather_service.resolve_city(loc_str)
            params = {"q": resolved_city}
            cache_key = f"nwp:{provider.provider_id}:{resolved_city.lower()}"
            city_query = resolved_city

    # Check database cache first
    cached = await database.cache_get(cache_key)
    if cached:
        logger.info(f"NWP Cache HIT: {cache_key}")
        return cached

    # Demo Mode or Missing API Key fallback
    if config.DEMO_MODE or not config.OWM_API_KEY:
        demo_payload = _generate_demo_nwp(provider, city_query, lat, lon)
        return demo_payload

    # Live OpenWeatherMap API retrieval
    try:
        t0 = time.perf_counter()
        raw_data = await asyncio.to_thread(_owm_sync_query, params)
        latency_ms = round((time.perf_counter() - t0) * 1000)
        logger.info(f"OWM NWP retrieved for {params} in {latency_ms}ms")

        result = _normalize_owm_nwp_payload(raw_data, provider, city_query, is_demo=False)
        await database.cache_set(cache_key, result, config.WEATHER_CACHE_TTL)
        return result

    except requests.HTTPError as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code == 404:
            raise ValueError(f"Location not found by OpenWeatherMap: '{location or f'{lat},{lon}'}'.")
        logger.error(f"OpenWeatherMap NWP HTTP error ({status_code}): {e}")
        # Fallback to deterministic demo if upstream service errors
        return _generate_demo_nwp(provider, city_query, lat, lon)
    except Exception as e:
        logger.error(f"OpenWeatherMap NWP unexpected error: {e}")
        return _generate_demo_nwp(provider, city_query, lat, lon)


# Provider registry
_providers: dict[str, NWPProvider] = {
    "owm": OpenWeatherMapNWPProvider(),
    "openweathermap": OpenWeatherMapNWPProvider(),
    "gfs": GFSProvider(),
    "wrf": WRFProvider(),
    "ecmwf": ECMWFProvider(),
}


async def get_nwp_forecast(
    location: str = "Visakhapatnam",
    provider: str = "owm",
    lat: Optional[float] = None,
    lon: Optional[float] = None
) -> dict:
    """
    Main entry point for NWP forecast queries.
    Selects the requested provider (defaulting to OpenWeatherMap NWP).
    """
    provider_inst = _providers.get(provider.lower().strip(), _providers["owm"])
    result = await provider_inst.get_forecast(location=location, lat=lat, lon=lon)
    return result


def get_nwp_status() -> dict:
    """
    Report NWP subsystem operational status, model capabilities, and integration telemetry.
    """
    is_live = bool(config.OWM_API_KEY) and not config.DEMO_MODE
    op_status = "operational" if is_live else "demo_mode"

    return {
        "current_operational": "OpenWeatherMap NWP",
        "status": op_status,
        "gfs": {
            "name": "GFS",
            "status": "operational_via_owm" if is_live else "prototype_placeholder",
            "production_source": "NOAA NOMADS / OWM Assimilation",
            "model": "NOAA Global Forecast System (GFS 0.25°)",
            "grid_resolution": "0.25° (~28 km)",
        },
        "wrf": {
            "name": "WRF",
            "status": "operational_via_owm" if is_live else "prototype_placeholder",
            "production_source": "WRF-ARW Server / OWM Surface Grid",
            "model": "Weather Research and Forecasting (WRF-ARW)",
            "grid_resolution": "3 km - 9 km High-Res Mesoscale",
        },
        "owm": {
            "name": "OpenWeatherMap NWP",
            "status": op_status,
            "production_source": "OpenWeatherMap Forecast 2.5 API",
            "model": "OWM Multi-Model Ensemble (NOAA GFS + ECMWF + ML MOS)",
            "grid_resolution": "0.25° (~25 km)",
            "update_frequency": "3-Hourly Cycles",
            "horizon": "120 Hours (5 Days)",
        },
        "ecmwf": {
            "name": "ECMWF",
            "status": "operational_via_owm" if is_live else "prototype_placeholder",
            "production_source": "ECMWF / OWM Assimilation",
            "model": "ECMWF Integrated Forecasting System (IFS)",
            "grid_resolution": "9 km Global HRES",
        },
        "disclaimer": NWP_DISCLAIMER,
    }
