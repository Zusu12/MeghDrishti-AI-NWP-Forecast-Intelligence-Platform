"""
advisory_service.py — Decision support for agriculture, aviation, marine, travel, outdoor, urban.
Combines deterministic meteorological rule engines with Gemini contextual enrichment.
Clearly distinguishes prototype recommendations from official safety instructions.
"""
import logging
from typing import Optional
import weather_service
import gemini_service

logger = logging.getLogger(__name__)

ADVISORY_DISCLAIMER = (
    "Prototype decision support derived from numerical forecast data. "
    "Not official government safety warnings or certified agronomic/aviation advice. "
    "Refer to IMD/NDMA/DGCA for statutory advisories."
)

ADVISORY_META = {
    "agriculture": {
        "icon": "🌾",
        "title": "Agriculture & Farming Advisory",
        "prompt_hint": "Give practical agronomic advice on irrigation timing, crop spraying suitability, and post-harvest protection.",
    },
    "aviation": {
        "icon": "✈️",
        "title": "Aviation Weather Briefing (Prototype)",
        "prompt_hint": "Summarise aviation parameters: visibility, surface wind shear, cloud ceiling, flight category (VFR/MVFR/IFR).",
    },
    "marine": {
        "icon": "🌊",
        "title": "Marine & Coastal Operations Advisory",
        "prompt_hint": "Assess sea state, Beaufort wind force, wave hazard indications, and small craft fishing suitability.",
    },
    "travel": {
        "icon": "🚗",
        "title": "Travel & Commute Advisory",
        "prompt_hint": "Assess road safety, visibility restrictions, aquaplaning risks, and recommended travel precautions.",
    },
    "outdoor": {
        "icon": "🏕️",
        "title": "Outdoor Activities & Public Events",
        "prompt_hint": "Advise on outdoor sports, open-air gatherings, heat stress, and thunderstorm sheltering precautions.",
    },
    "urban": {
        "icon": "🏙️",
        "title": "Urban Infrastructure & City Impact",
        "prompt_hint": "Assess municipal drainage impact, localized waterlogging probability, urban heat island intensity, and public transit.",
    },
}


def _generate_deterministic_advisory(mode: str, weather: dict, forecast: list) -> str:
    """Deterministic rule-based decision logic based on verified meteorological metrics."""
    temp = weather.get("temperature", 25.0)
    wind = weather.get("wind_speed", 10.0)
    rain = weather.get("rain_1h", 0.0)
    hum = weather.get("humidity", 60)
    vis = weather.get("visibility", 10000)
    cond = weather.get("condition", "Clear")
    cid = weather.get("condition_id", 800)

    # Forecast rain & thunderstorm check in next 24h
    max_pop = 0
    max_forecast_rain = 0.0
    forecast_ts = False
    if forecast:
        for slot in forecast[:8]:
            max_pop = max(max_pop, int(slot.get("pop", 0) * 100))
            max_forecast_rain = max(max_forecast_rain, slot.get("rain_3h", 0.0))
            if 200 <= slot.get("condition_id", 800) <= 232:
                forecast_ts = True

    if mode == "agriculture":
        if max_pop >= 50 or rain > 2.0 or max_forecast_rain >= 5.0:
            return (
                f"🌧️ High precipitation probability ({max_pop}%) expected over the next 24 hours. "
                "Consider temporarily suspending artificial irrigation and postponing foliar pesticide/fertilizer spraying "
                "to prevent runoff loss. Ensure drainage outlets in low-lying crop fields are clear to avert waterlogging."
            )
        elif temp >= 38.0 and hum < 50:
            return (
                f"🌡️ High ambient temperatures ({temp}°C) and low humidity ({hum}%) indicate elevated evapotranspiration rates. "
                "Schedule light irrigation cycles during early morning or late evening hours to conserve soil moisture. "
                "Provide protective shade nets for tender seedlings and newly planted saplings."
            )
        else:
            return (
                f"🌾 Weather conditions are generally favorable (Temperature: {temp}°C, Humidity: {hum}%). "
                "Suitable window for routine harvesting, soil conditioning, weeding, and balanced fertilizer application."
            )

    elif mode == "aviation":
        category = "VFR"
        if vis < 3000 or cid in range(200, 233):
            category = "IFR"
        elif vis < 5000 or weather.get("cloud_cover", 0) > 75:
            category = "MVFR"

        return (
            f"✈️ Prototype Aviation Summary — Estimated Flight Rules: **{category}**. "
            f"Surface Wind: {wind} km/h (direction {weather.get('wind_deg', 0)}°). "
            f"Visibility: {round(vis / 1000, 1)} km. Cloud Cover: {weather.get('cloud_cover', 0)}%. "
            f"Precipitation: {rain} mm/hr. "
            f"{'⚠️ Convective thunderstorm activity indicated in vicinity.' if forecast_ts or (200 <= cid <= 232) else 'No active thunderstorm convective cells detected.'}"
        )

    elif mode == "marine":
        # Beaufort scale approximation
        if wind >= 50 or (200 <= cid <= 232):
            return (
                f"🌊 Squally and turbulent sea conditions expected with winds reaching {wind} km/h. "
                "Small craft operators and coastal fishermen are strongly advised to avoid venturing into open deep waters. "
                "Secure moored boats and shoreline equipment against wave action."
            )
        elif wind >= 28:
            return (
                f"🌊 Moderate to choppy sea state with surface winds around {wind} km/h. "
                "Caution is advised for artisanal fishing boats, small catamarans, and recreational watercraft. Maintain continuous VHF radio watch."
            )
        else:
            return (
                f"⛵ Favorable marine conditions. Surface wind is gentle at {wind} km/h with clear visibility ({round(vis / 1000, 1)} km). "
                "Generally safe for coastal navigation, harbor operations, and inshore fishing activities."
            )

    elif mode == "travel":
        if vis <= 500:
            return (
                f"🌫️ Dense fog / severely impaired visibility ({vis} meters) reported. "
                "Reduce driving speed significantly, utilize low-beam fog lights, avoid abrupt lane transitions, and expect substantial highway delays."
            )
        elif rain >= 5.0 or max_pop >= 70:
            return (
                f"🌧️ Wet roadway surfaces and reduced tire traction anticipated with rain ({rain} mm/hr, PoP: {max_pop}%). "
                "Allow 15–20% additional commute time, carry rain protection, and maintain increased braking intervals to prevent aquaplaning."
            )
        else:
            return (
                f"🚗 Highway and city commute conditions are clear and unobstructed. "
                f"Visibility is excellent at {round(vis / 1000, 1)} km with smooth transit expected."
            )

    elif mode == "outdoor":
        if 200 <= cid <= 232 or forecast_ts:
            return (
                "⛈️ Thunderstorm and lightning hazards identified in the area. "
                "All open-ground sports, swimming, picnics, and high-elevation outdoor activities should be postponed. "
                "Seek enclosed shelter away from solitary trees or metal structures."
            )
        elif temp >= 40.0:
            return (
                f"☀️ Severe heat stress risk (Current temperature: {temp}°C, Feels like: {weather.get('feels_like', temp)}°C). "
                "Avoid strenuous outdoor exertion between 11:30 and 15:30. Ensure electrolyte replenishment and wear light cotton clothing."
            )
        else:
            return (
                f"🏕️ Pleasant and stable weather ({temp}°C, {cond}). "
                "Ideal conditions for outdoor events, trekking, fitness routines, and recreational park activities."
            )

    elif mode == "urban":
        if rain >= 10.0 or max_forecast_rain >= 15.0:
            return (
                f"🏙️ Heavy rainfall rate ({rain} mm/hr) creates high potential for localized waterlogging, slow storm-water runoff, "
                "and underpass inundation. Municipal authorities and motorists should monitor critical arterial intersections."
            )
        else:
            return (
                f"🏙️ City environmental parameters: Temperature {temp}°C, Atmospheric Pressure {weather.get('pressure', 1013)} hPa, "
                f"Humidity {hum}%. Normal municipal transit flow and drainage functionality expected."
            )

    return f"Advisory for {weather.get('location')}: {cond}, {temp}°C with wind at {wind} km/h."


async def get_advisory(location: str, mode: str, language: str = "en") -> dict:
    mode = mode.lower()
    meta = ADVISORY_META.get(mode, ADVISORY_META["travel"])

    try:
        weather = await weather_service.get_current_weather(location)
        forecast = await weather_service.get_forecast(location)
    except (ValueError, RuntimeError) as e:
        return {"error": str(e), "mode": mode}

    deterministic_advice = _generate_deterministic_advisory(mode, weather, forecast)

    # If Gemini is available, produce an enriched explanation grounded in the deterministic advice
    enriched_advisory = deterministic_advice
    try:
        query = f"Provide a detailed, practical {mode} advisory for {weather.get('location')}. {meta['prompt_hint']} Base findings on: {deterministic_advice}"
        gemini_result = await gemini_service.generate_response(
            query=query,
            weather=weather,
            forecast=forecast,
            intent={"type": mode, "advisory_mode": mode},
            advisory_mode=mode,
            language=language,
        )
        if gemini_result and len(gemini_result) > 20:
            enriched_advisory = gemini_result
    except Exception as e:
        logger.warning(f"Advisory enrichment fallback used: {e}")
        enriched_advisory = deterministic_advice

    return {
        "mode": mode,
        "icon": meta["icon"],
        "title": meta["title"],
        "location": weather.get("location"),
        "weather": {
            "temperature": weather.get("temperature"),
            "feels_like": weather.get("feels_like"),
            "condition": weather.get("condition"),
            "humidity": weather.get("humidity"),
            "wind_speed": weather.get("wind_speed"),
            "rain_1h": weather.get("rain_1h", 0),
            "visibility": weather.get("visibility", 10000),
        },
        "advisory": enriched_advisory,
        "deterministic_base": deterministic_advice,
        "disclaimer": ADVISORY_DISCLAIMER,
        "demo": weather.get("demo", False),
    }
