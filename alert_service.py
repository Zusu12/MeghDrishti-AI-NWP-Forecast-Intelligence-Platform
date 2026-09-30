"""
alert_service.py — Extreme weather risk evaluation & Official IMD/NDMA Warning Integration.
Combines deterministic meteorological threshold detection with official IMD 4-color coded
district bulletins and OASIS / ITU-T X.1303 CAP v1.2 warning documents.
"""
import logging
from typing import Optional

import imd_service

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ Official IMD & NDMA Common Alerting Protocol (CAP v1.2) integration feed. "
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
    return a if SEVERITY_ORDER.get(a, 0) >= SEVERITY_ORDER.get(b, 0) else b


def check_alerts(weather: dict, forecast=None, location: Optional[str] = None) -> dict:
    """
    Evaluate severe weather risk using both deterministic meteorological rules
    and official IMD 4-Color District Warning / NDMA CAP v1.2 protocols.
    """
    alerts = []
    max_severity = "INFO"

    cid = weather.get("condition_id", 800)
    temp = weather.get("temperature", 25)
    wind = weather.get("wind_speed", 0)
    rain_1h = weather.get("rain_1h", 0)
    visibility = weather.get("visibility", 10000)
    loc_str = location or weather.get("location", "Visakhapatnam")

    # 1. Thunderstorm Detection
    if THRESHOLDS["thunderstorm_id_min"] <= cid <= THRESHOLDS["thunderstorm_id_max"]:
        sev = "HIGH"
        alerts.append({
            "type": "thunderstorm",
            "severity": sev,
            "message": "Thunderstorm conditions detected. Avoid outdoor activities.",
            "icon": "⛈️"
        })
        max_severity = _sev(max_severity, sev)

    # 2. Extreme Storm
    if THRESHOLDS["storm_id_min"] <= cid <= THRESHOLDS["storm_id_max"]:
        sev = "HIGH"
        alerts.append({
            "type": "storm",
            "severity": sev,
            "message": "Extreme storm conditions. Seek immediate shelter.",
            "icon": "🌪️"
        })
        max_severity = _sev(max_severity, sev)

    # 3. Heavy Rain
    if rain_1h >= THRESHOLDS["heavy_rain_1h"]:
        sev = "WARNING" if rain_1h < 20 else "HIGH"
        alerts.append({
            "type": "heavy_rain",
            "severity": sev,
            "message": f"Heavy rainfall: {rain_1h} mm/hr. Flooding possible.",
            "icon": "🌧️"
        })
        max_severity = _sev(max_severity, sev)

    # 4. Extreme Heat
    if temp >= THRESHOLDS["extreme_heat"]:
        sev = "HIGH" if temp >= 45 else "WARNING"
        alerts.append({
            "type": "extreme_heat",
            "severity": sev,
            "message": f"Extreme heat: {temp}°C. Heat stroke risk.",
            "icon": "🌡️"
        })
        max_severity = _sev(max_severity, sev)

    # 5. Extreme Cold
    if temp <= THRESHOLDS["extreme_cold"]:
        sev = "WARNING" if temp > 0 else "HIGH"
        alerts.append({
            "type": "extreme_cold",
            "severity": sev,
            "message": f"Extreme cold: {temp}°C. Hypothermia risk.",
            "icon": "🥶"
        })
        max_severity = _sev(max_severity, sev)

    # 6. Strong Winds
    if wind >= THRESHOLDS["strong_wind_kmh"]:
        sev = "WARNING" if wind < 80 else "HIGH"
        alerts.append({
            "type": "strong_wind",
            "severity": sev,
            "message": f"Strong winds: {wind} km/h. Marine and aviation caution.",
            "icon": "💨"
        })
        max_severity = _sev(max_severity, sev)

    # 7. Poor Visibility
    if visibility <= THRESHOLDS["poor_visibility_m"]:
        sev = "WATCH"
        alerts.append({
            "type": "poor_visibility",
            "severity": sev,
            "message": f"Poor visibility: {visibility}m. Drive with caution.",
            "icon": "🌫️"
        })
        max_severity = _sev(max_severity, sev)

    # 8. Forecast Scan
    if forecast:
        for slot in forecast[:8]:
            if slot.get("rain_3h", 0) >= THRESHOLDS["heavy_rain_3h"] or slot.get("pop", 0) >= 0.8:
                sev = "WATCH"
                alerts.append({
                    "type": "forecast_rain",
                    "severity": sev,
                    "message": "Heavy rainfall likely in the next 24 hours.",
                    "icon": "🌧️"
                })
                max_severity = _sev(max_severity, sev)
                break

        for slot in forecast[:8]:
            cid_f = slot.get("condition_id", 800)
            if THRESHOLDS["thunderstorm_id_min"] <= cid_f <= THRESHOLDS["thunderstorm_id_max"]:
                sev = "WATCH"
                alerts.append({
                    "type": "forecast_thunderstorm",
                    "severity": sev,
                    "message": "Thunderstorm expected in the next 24 hours.",
                    "icon": "⛈️"
                })
                max_severity = _sev(max_severity, sev)
                break

    # 9. Official IMD & NDMA CAP Warning Integration
    cap_doc = imd_service.evaluate_official_imd_alert(
        location=loc_str,
        weather_data=weather,
        forecast_list=forecast,
        lat=weather.get("lat"),
        lon=weather.get("lon"),
    )
    cap_info = cap_doc.get("info", {})
    imd_color = cap_info.get("color_code", "GREEN")

    color_severity_map = {
        "RED": "HIGH",
        "ORANGE": "WARNING",
        "YELLOW": "WATCH",
        "GREEN": "INFO",
    }
    imd_sev = color_severity_map.get(imd_color, "INFO")
    if imd_sev != "INFO":
        max_severity = _sev(max_severity, imd_sev)

    has_alert = len(alerts) > 0 or imd_color in ["YELLOW", "ORANGE", "RED"]

    return {
        "alert": has_alert,
        "severity": max_severity if has_alert else "INFO",
        "alerts": alerts,
        "imd_warning": {
            "color_code": imd_color,
            "color_name": cap_info.get("color_name", "No Warning"),
            "action": cap_info.get("color_action", "No Action"),
            "color_hex": cap_info.get("color_hex", "#15803D"),
            "bg_hex": cap_info.get("bg_hex", "#DCFCE7"),
            "headline": cap_info.get("headline", ""),
            "bulletin_id": cap_doc.get("identifier", ""),
            "sender": cap_info.get("senderName", "India Meteorological Department"),
            "area": cap_info.get("area", {}).get("areaDesc", loc_str),
            "instruction": cap_info.get("instruction", ""),
            "hazards": cap_info.get("hazards", []),
        },
        "cap_document": cap_doc,
        "disclaimer": DISCLAIMER,
        "demo": weather.get("demo", False),
    }
