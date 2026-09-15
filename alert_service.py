"""
alert_service.py — Rule-based extreme weather alert detection
NOT official government warnings — clearly labelled prototype risk indicators.
"""
import logging

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ Forecast-derived risk indication. "
    "Check official government advisories (IMD/NDMA) for authoritative warnings."
)

THRESHOLDS = {
    "heavy_rain_1h": 7.6,
    "heavy_rain_3h": 15.0,
    "extreme_heat": 42.0,
    "extreme_cold": 5.0,
    "strong_wind_kmh": 50.0,
    "poor_visibility_m": 200,
    "thunderstorm_id_min": 200,
    "thunderstorm_id_max": 232,
    "storm_id_min": 900,
    "storm_id_max": 902,
}

SEVERITY_ORDER = {"INFO": 0, "WATCH": 1, "WARNING": 2, "HIGH": 3}


def _sev(a: str, b: str) -> str:
    return a if SEVERITY_ORDER[a] >= SEVERITY_ORDER[b] else b


def check_alerts(weather: dict, forecast=None) -> dict:
    alerts = []
    max_severity = "INFO"

    cid = weather.get("condition_id", 800)
    temp = weather.get("temperature", 25)
    wind = weather.get("wind_speed", 0)
    rain_1h = weather.get("rain_1h", 0)
    visibility = weather.get("visibility", 10000)

    # Thunderstorm
    if THRESHOLDS["thunderstorm_id_min"] <= cid <= THRESHOLDS["thunderstorm_id_max"]:
        sev = "HIGH"
        alerts.append({"type": "thunderstorm", "severity": sev,
                       "message": "Thunderstorm conditions detected. Avoid outdoor activities.", "icon": "⛈️"})
        max_severity = _sev(max_severity, sev)

    # Extreme storm
    if THRESHOLDS["storm_id_min"] <= cid <= THRESHOLDS["storm_id_max"]:
        sev = "HIGH"
        alerts.append({"type": "storm", "severity": sev,
                       "message": "Extreme storm conditions. Seek immediate shelter.", "icon": "🌪️"})
        max_severity = _sev(max_severity, sev)

    # Heavy rain
    if rain_1h >= THRESHOLDS["heavy_rain_1h"]:
        sev = "WARNING" if rain_1h < 20 else "HIGH"
        alerts.append({"type": "heavy_rain", "severity": sev,
                       "message": f"Heavy rainfall: {rain_1h} mm/hr. Flooding possible.", "icon": "🌧️"})
        max_severity = _sev(max_severity, sev)

    # Extreme heat
    if temp >= THRESHOLDS["extreme_heat"]:
        sev = "HIGH" if temp >= 45 else "WARNING"
        alerts.append({"type": "extreme_heat", "severity": sev,
                       "message": f"Extreme heat: {temp}°C. Heat stroke risk.", "icon": "🌡️"})
        max_severity = _sev(max_severity, sev)

    # Extreme cold
    if temp <= THRESHOLDS["extreme_cold"]:
        sev = "WARNING" if temp > 0 else "HIGH"
        alerts.append({"type": "extreme_cold", "severity": sev,
                       "message": f"Extreme cold: {temp}°C. Hypothermia risk.", "icon": "🥶"})
        max_severity = _sev(max_severity, sev)

    # Strong winds
    if wind >= THRESHOLDS["strong_wind_kmh"]:
        sev = "WARNING" if wind < 80 else "HIGH"
        alerts.append({"type": "strong_wind", "severity": sev,
                       "message": f"Strong winds: {wind} km/h. Marine and aviation caution.", "icon": "💨"})
        max_severity = _sev(max_severity, sev)

    # Poor visibility
    if visibility <= THRESHOLDS["poor_visibility_m"]:
        sev = "WATCH"
        alerts.append({"type": "poor_visibility", "severity": sev,
                       "message": f"Poor visibility: {visibility}m. Drive with caution.", "icon": "🌫️"})
        max_severity = _sev(max_severity, sev)

    # Forecast scan
    if forecast:
        for slot in forecast[:8]:
            if slot.get("rain_3h", 0) >= THRESHOLDS["heavy_rain_3h"] or slot.get("pop", 0) >= 0.8:
                sev = "WATCH"
                alerts.append({"type": "forecast_rain", "severity": sev,
                               "message": "Heavy rainfall likely in the next 24 hours.", "icon": "🌧️"})
                max_severity = _sev(max_severity, sev)
                break

        for slot in forecast[:8]:
            cid_f = slot.get("condition_id", 800)
            if THRESHOLDS["thunderstorm_id_min"] <= cid_f <= THRESHOLDS["thunderstorm_id_max"]:
                sev = "WATCH"
                alerts.append({"type": "forecast_thunderstorm", "severity": sev,
                               "message": "Thunderstorm expected in the next 24 hours.", "icon": "⛈️"})
                max_severity = _sev(max_severity, sev)
                break

    has_alert = len(alerts) > 0
    return {
        "alert": has_alert,
        "severity": max_severity if has_alert else "INFO",
        "alerts": alerts,
        "disclaimer": DISCLAIMER,
        "demo": weather.get("demo", False),
    }
