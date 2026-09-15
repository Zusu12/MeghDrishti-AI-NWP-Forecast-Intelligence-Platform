"""
gemini_service.py — Google Gemini AI integration
Uses google-genai SDK. Gemini NEVER invents weather values.
Includes multi-model fallback, multilingual generation, and deterministic offline fallbacks.
"""
import json
import logging
import time
import re
from typing import Optional

import config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not configured.")
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _get_candidate_models() -> list[str]:
    primary = config.GEMINI_MODEL
    fallbacks = [m for m in config.GEMINI_FALLBACK_MODELS if m != primary]
    return [primary] + fallbacks


INTENT_PROMPT = """You are a meteorological query parser. Extract structured intent from the user's weather question.
Return ONLY valid JSON — no markdown fences, no extra commentary.

Schema:
{{
  "location": "<city or place name extracted from query, or null if not mentioned>",
  "date": "<today|tomorrow|day_after|this_week|null>",
  "variable": "<rain|temperature|wind|humidity|visibility|cloud|general|forecast>",
  "type": "<general|rain|temperature|wind|humidity|forecast|recommendation|warning|comparison|trend|agriculture|marine|aviation|urban>",
  "advisory_mode": "<agriculture|marine|aviation|urban|travel|outdoor|null>"
}}

User query: {query}
"""

RESPONSE_PROMPT = """You are WeatherGPT, an AI weather intelligence assistant for India (Ministry of Earth Sciences, SIH 2026).

STRICT METEOROLOGICAL RULES:
1. Base all facts STRICTLY on the weather data provided below. NEVER fabricate or extrapolate unverified weather metrics.
2. Be concise, actionable, and courteous (2-4 sentences for standard questions).
3. If giving an advisory or recommendation, preface with "Based on current forecasts...".
4. Do NOT make professional safety-critical declarations (IMD/NDMA are the authoritative bodies).
5. Language instruction: {language_instruction}

Location: {location}
Current Weather:
{weather_json}

Forecast (Next 24h intervals):
{forecast_summary}

User Query: {query}
{advisory_section}

Response:"""


def _safe_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _heuristic_intent(query: str) -> dict:
    """Fast deterministic intent extraction as offline fallback."""
    q = query.lower()
    
    # Location extraction hints
    known_cities = [
        "visakhapatnam", "vizag", "delhi", "mumbai", "bombay", "chennai", "madras",
        "kolkata", "bengaluru", "bangalore", "hyderabad", "pune", "ahmedabad",
        "jaipur", "lucknow", "chandigarh", "kochi", "cochin", "goa", "bhopal",
        "varanasi", "thiruvananthapuram", "patna", "bhubaneswar", "guwahati"
    ]
    detected_loc = None
    for city in known_cities:
        if city in q:
            detected_loc = city.title()
            break

    # Date
    date = "today"
    if "tomorrow" in q or "कल" in q or "రేపు" in q:
        date = "tomorrow"
    elif "week" in q or "హఫ్తా" in q or "వారం" in q:
        date = "this_week"

    # Advisory
    advisory_mode = None
    if any(w in q for w in ["farm", "crop", "irrigation", "agriculture", "खेती", "రైతు", "వ్యవసాయ"]):
        advisory_mode = "agriculture"
    elif any(w in q for w in ["aviation", "flight", "pilot", "विमान"]):
        advisory_mode = "aviation"
    elif any(w in q for w in ["marine", "sea", "boat", "fisher", "సముద్రం", "मछली"]):
        advisory_mode = "marine"
    elif any(w in q for w in ["travel", "drive", "road", "यात्रा", "ప్రయాణం"]):
        advisory_mode = "travel"
    elif any(w in q for w in ["outdoor", "picnic", "run", "park"]):
        advisory_mode = "outdoor"

    # Variable
    variable = "general"
    q_type = "general"
    if any(w in q for w in ["rain", "precipitation", "umbrella", "shower", "बारिश", "వర్షం"]):
        variable = "rain"
        q_type = "rain"
    elif any(w in q for w in ["temp", "hot", "cold", "heat", "तापमान", "వేడి", "చలి"]):
        variable = "temperature"
        q_type = "temperature"
    elif any(w in q for w in ["wind", "storm", "cyclone", "గాలి", "తుఫాను"]):
        variable = "wind"
        q_type = "warning"

    return {
        "location": detected_loc,
        "date": date,
        "variable": variable,
        "type": q_type,
        "advisory_mode": advisory_mode,
    }


async def parse_intent(query: str) -> dict:
    """Parse user query intent with Gemini and multi-model fallback."""
    if not config.GEMINI_API_KEY:
        return _heuristic_intent(query)

    client = None
    try:
        client = _get_client()
    except Exception as e:
        logger.warning(f"Could not init Gemini client: {e}")
        return _heuristic_intent(query)

    for model in _get_candidate_models():
        try:
            t0 = time.perf_counter()
            response = client.models.generate_content(
                model=model,
                contents=INTENT_PROMPT.format(query=query),
            )
            data = _safe_json(response.text)
            logger.info(f"Gemini intent parsed [{model}]: {round((time.perf_counter()-t0)*1000)}ms")
            return data
        except Exception as e:
            logger.warning(f"Gemini intent parsing failed on model {model}: {e}")
            continue

    # Fall back gracefully to heuristics
    return _heuristic_intent(query)


def _forecast_summary(forecast: list) -> str:
    if not forecast:
        return "No forecast intervals available."
    from datetime import datetime, timezone
    lines = []
    for slot in forecast[:8]:
        dt = datetime.fromtimestamp(slot.get("dt", 0), tz=timezone.utc).strftime("%a %H:%M UTC")
        rain = slot.get("rain_3h", 0)
        pop = int(slot.get("pop", 0) * 100)
        lines.append(
            f"  {dt}: {slot.get('condition', 'Clear')}, {slot.get('temperature', '--')}°C, "
            f"Rain: {rain}mm, PoP: {pop}%"
        )
    return "\n".join(lines)


def _deterministic_weather_summary(weather: dict, forecast: list, language: str = "en") -> str:
    """Factual, friendly fallback message in requested language when AI quota/network fails."""
    loc = weather.get("location", "the requested city")
    temp = weather.get("temperature", "--")
    feels = weather.get("feels_like", temp)
    cond = weather.get("condition", "clear")
    hum = weather.get("humidity", "--")
    wind = weather.get("wind_speed", "--")

    # Check rain probability in next 24h
    max_pop = 0
    if forecast:
        max_pop = int(max([f.get("pop", 0) for f in forecast[:8]]) * 100)

    if language == "hi":
        msg = (
            f"{loc} में वर्तमान मौसम {cond} है और तापमान {temp}°C (अनुभव {feels}°C) है। "
            f"हवा में आर्द्रता {hum}% तथा हवा की गति {wind} किमी/घंटा है। "
        )
        if max_pop > 40:
            msg += f"अगले 24 घंटों में बारिश की संभावना लगभग {max_pop}% है, छाता साथ रखें।"
        else:
            msg += f"अगले 24 घंटों में मौसम मुख्यतः स्थिर रहने की संभावना है (बारिश की संभावना {max_pop}%)।"
        return msg

    elif language == "te":
        msg = (
            f"{loc}లో ప్రస్తుత వాతావరణం {cond} మరియు ఉష్ణోగ్రత {temp}°C (అనిపించేది {feels}°C). "
            f"గాలిలో తేమ {hum}% మరియు గాలి వేగం {wind} కి.మీ/గం ఉంది. "
        )
        if max_pop > 40:
            msg += f"రాబోయే 24 గంటల్లో వర్షం పడే అవకాశం సుమారు {max_pop}% ఉంది, గొడుగు వెంట ఉంచుకోండి."
        else:
            msg += f"రాబోయే 24 గంటల్లో వాతావరణం అనుకూలంగా ఉండవచ్చు (వర్షం అవకాశం {max_pop}%)."
        return msg

    else:
        msg = (
            f"In {loc}, it is currently {temp}°C ({cond}) with feels-like {feels}°C. "
            f"Humidity is at {hum}% with wind speeds of {wind} km/h. "
        )
        if max_pop > 40:
            msg += f"Forecast models indicate a {max_pop}% chance of precipitation over the next 24 hours."
        else:
            msg += f"Conditions are expected to remain relatively stable with a low rain chance of {max_pop}%."
        return msg


async def generate_response(
    query: str,
    weather: dict,
    forecast: list,
    intent: dict,
    advisory_mode: Optional[str] = None,
    language: str = "en",
) -> str:
    """
    Generate conversational weather response with Google Gemini.
    Generates directly in requested language (en/hi/te).
    Falls back gracefully to deterministic factual summary if API unavailable.
    """
    if not config.GEMINI_API_KEY or weather.get("demo") and config.DEMO_MODE:
        return _deterministic_weather_summary(weather, forecast, language)

    # Configure language-specific prompt instructions
    if language == "hi":
        lang_instruction = "Respond entirely in fluent, natural Hindi (Devanagari script). Use standard Hindi weather terminology."
    elif language == "te":
        lang_instruction = "Respond entirely in fluent, natural Telugu (Telugu script). Use standard Telugu weather terminology."
    else:
        lang_instruction = "Respond in fluent, friendly, and concise English."

    advisory_section = ""
    if advisory_mode:
        advisory_section = f"Sector Advisory Request: {advisory_mode.upper()} sector. Provide practical recommendations for this sector."

    prompt = RESPONSE_PROMPT.format(
        location=weather.get("location", "Unknown"),
        weather_json=json.dumps(weather, indent=2),
        forecast_summary=_forecast_summary(forecast),
        query=query,
        language_instruction=lang_instruction,
        advisory_section=advisory_section,
    )

    client = None
    try:
        client = _get_client()
    except Exception as e:
        logger.warning(f"Gemini client init error: {e}")
        return _deterministic_weather_summary(weather, forecast, language)

    for model in _get_candidate_models():
        try:
            t0 = time.perf_counter()
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            text = response.text.strip()
            logger.info(f"Gemini response generated [{model}] in {round((time.perf_counter()-t0)*1000)}ms")
            return text
        except Exception as e:
            logger.warning(f"Gemini response generation failed on model {model}: {e}")
            continue

    # If all models fail (e.g. rate limit, 503 spike, network drop):
    logger.info("Using deterministic factual weather summary fallback.")
    return _deterministic_weather_summary(weather, forecast, language)
