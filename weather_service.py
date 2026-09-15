"""
weather_service.py — OpenWeatherMap integration with caching, coordinate lookup, and city alias resolution.
All weather values come from the API — Gemini never invents data.
"""
import time
import logging
from typing import Optional, Union
import requests
import config
import database

logger = logging.getLogger(__name__)

CITY_ALIASES = {
    "vizag": "Visakhapatnam",
    "bombay": "Mumbai",
    "madras": "Chennai",
    "calcutta": "Kolkata",
    "bangalore": "Bengaluru",
    "poona": "Pune",
    "benares": "Varanasi",
    "trivandrum": "Thiruvananthapuram",
    "cochin": "Kochi",
    "calicut": "Kozhikode",
}

DEMO_WEATHER = {
    "location": "Visakhapatnam (DEMO)",
    "country": "IN",
    "temperature": 29.0,
    "feels_like": 32.0,
    "temp_min": 27.0,
    "temp_max": 31.5,
    "humidity": 78,
    "pressure": 1010,
    "wind_speed": 14.0,
    "wind_deg": 180,
    "visibility": 8000,
    "cloud_cover": 60,
    "condition": "Light Rain",
    "condition_id": 500,
    "icon": "10d",
    "rain_1h": 1.2,
    "lat": 17.6868,
    "lon": 83.2185,
    "sunrise": int(time.time()) - 14400,
    "sunset": int(time.time()) + 28800,
    "demo": True,
}

DEMO_FORECAST = [
    {
        "dt": int(time.time()) + i * 10800,
        "temperature": round(28.0 + (i % 4) * 1.2, 1),
        "feels_like": round(31.0 + (i % 3) * 1.5, 1),
        "humidity": 75 + (i % 10),
        "wind_speed": round(12.0 + (i % 5) * 2.1, 1),
        "condition": ["Light Rain", "Partly Cloudy", "Thunderstorm", "Clear Sky"][i % 4],
        "condition_id": [500, 802, 211, 800][i % 4],
        "icon": ["10d", "03d", "11d", "01d"][i % 4],
        "rain_3h": [1.5, 0.0, 8.0, 0.0][i % 4],
        "pop": [0.6, 0.2, 0.9, 0.05][i % 4],
        "demo": True,
    }
    for i in range(40)
]


def resolve_city(location: str) -> str:
    return CITY_ALIASES.get(location.lower().strip(), location.strip())


def _normalize_current_payload(data: dict, is_demo: bool = False) -> dict:
    return {
        "location": data.get("name", "Unknown"),
        "country": data.get("sys", {}).get("country", "IN"),
        "temperature": round(data.get("main", {}).get("temp", 0), 1),
        "feels_like": round(data.get("main", {}).get("feels_like", 0), 1),
        "temp_min": round(data.get("main", {}).get("temp_min", 0), 1),
        "temp_max": round(data.get("main", {}).get("temp_max", 0), 1),
        "humidity": data.get("main", {}).get("humidity", 0),
        "pressure": data.get("main", {}).get("pressure", 1013),
        "wind_speed": round(data.get("wind", {}).get("speed", 0) * 3.6, 1),  # m/s to km/h
        "wind_deg": data.get("wind", {}).get("deg", 0),
        "visibility": data.get("visibility", 10000),
        "cloud_cover": data.get("clouds", {}).get("all", 0),
        "condition": data.get("weather", [{}])[0].get("description", "Clear").title(),
        "condition_id": data.get("weather", [{}])[0].get("id", 800),
        "icon": data.get("weather", [{}])[0].get("icon", "01d"),
        "rain_1h": data.get("rain", {}).get("1h", 0.0),
        "lat": data.get("coord", {}).get("lat", 0.0),
        "lon": data.get("coord", {}).get("lon", 0.0),
        "sunrise": data.get("sys", {}).get("sunrise", 0),
        "sunset": data.get("sys", {}).get("sunset", 0),
        "demo": is_demo,
    }


def _normalize_forecast_payload(data: dict, is_demo: bool = False) -> list:
    forecast_list = []
    for item in data.get("list", []):
        forecast_list.append({
            "dt": item.get("dt", 0),
            "temperature": round(item.get("main", {}).get("temp", 0), 1),
            "feels_like": round(item.get("main", {}).get("feels_like", 0), 1),
            "humidity": item.get("main", {}).get("humidity", 0),
            "wind_speed": round(item.get("wind", {}).get("speed", 0) * 3.6, 1),
            "condition": item.get("weather", [{}])[0].get("description", "Clear").title(),
            "condition_id": item.get("weather", [{}])[0].get("id", 800),
            "icon": item.get("weather", [{}])[0].get("icon", "01d"),
            "rain_3h": item.get("rain", {}).get("3h", 0.0),
            "pop": item.get("pop", 0.0),
            "demo": is_demo,
        })
    return forecast_list


def _owm_current_query(params: dict) -> dict:
    url = f"{config.OWM_BASE_URL}/weather"
    params["appid"] = config.OWM_API_KEY
    params["units"] = "metric"
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return _normalize_current_payload(resp.json())


def _owm_forecast_query(params: dict) -> list:
    url = f"{config.OWM_BASE_URL}/forecast"
    params["appid"] = config.OWM_API_KEY
    params["units"] = "metric"
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return _normalize_forecast_payload(resp.json())


async def get_current_weather(location: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> dict:
    """
    Retrieve current weather conditions either by city name or latitude/longitude coordinates.
    """
    cache_key = ""
    params = {}
    city = ""

    if lat is not None and lon is not None:
        params = {"lat": round(lat, 4), "lon": round(lon, 4)}
        cache_key = f"current:coords:{round(lat, 2)}:{round(lon, 2)}"
    else:
        city = resolve_city(location or "Visakhapatnam")
        params = {"q": city}
        cache_key = f"current:{city.lower()}"

    cached = await database.cache_get(cache_key)
    if cached:
        logger.info(f"Cache HIT current: {cache_key}")
        return cached

    if config.DEMO_MODE:
        demo = dict(DEMO_WEATHER)
        if city:
            demo["location"] = f"{city} (DEMO)"
        elif lat and lon:
            demo["location"] = f"Lat {round(lat,2)}, Lon {round(lon,2)} (DEMO)"
            demo["lat"] = lat
            demo["lon"] = lon
        return demo

    try:
        t0 = time.perf_counter()
        data = _owm_current_query(params)
        logger.info(f"OWM current retrieved for {params} in {round((time.perf_counter()-t0)*1000)}ms")
        await database.cache_set(cache_key, data, config.WEATHER_CACHE_TTL)
        return data
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise ValueError(f"Location not found: '{location or f'{lat},{lon}'}'. Please verify spelling or coordinates.")
        raise RuntimeError(f"OpenWeatherMap service error: {e}")
    except Exception as e:
        logger.error(f"OWM current error: {e}")
        raise RuntimeError(f"Could not fetch weather data: {e}")


async def get_forecast(location: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> list:
    """
    Retrieve 5-day weather forecast either by city name or latitude/longitude coordinates.
    """
    cache_key = ""
    params = {}
    city = ""

    if lat is not None and lon is not None:
        params = {"lat": round(lat, 4), "lon": round(lon, 4)}
        cache_key = f"forecast:coords:{round(lat, 2)}:{round(lon, 2)}"
    else:
        city = resolve_city(location or "Visakhapatnam")
        params = {"q": city}
        cache_key = f"forecast:{city.lower()}"

    cached = await database.cache_get(cache_key)
    if cached:
        logger.info(f"Cache HIT forecast: {cache_key}")
        return cached

    if config.DEMO_MODE:
        return [dict(f) for f in DEMO_FORECAST]

    try:
        t0 = time.perf_counter()
        data = _owm_forecast_query(params)
        logger.info(f"OWM forecast retrieved for {params} in {round((time.perf_counter()-t0)*1000)}ms")
        await database.cache_set(cache_key, data, config.WEATHER_CACHE_TTL)
        return data
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            raise ValueError(f"Location not found: '{location or f'{lat},{lon}'}'.")
        raise RuntimeError(f"OpenWeatherMap service error: {e}")
    except Exception as e:
        logger.error(f"OWM forecast error: {e}")
        raise RuntimeError(f"Could not fetch forecast: {e}")
