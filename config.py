"""
config.py — MeghDrishti centralised configuration
All environment variables are loaded here. Services import from this module.
Railway deployment: uses $PORT for dynamic port binding.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (same directory as this file)
load_dotenv(Path(__file__).parent / ".env")


# ── Gemini ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODELS: list[str] = ["gemini-3.6-flash", "gemini-flash-latest"]

# ── OpenWeatherMap ─────────────────────────────────────────────────────────────
OWM_API_KEY: str = os.getenv("OPENWEATHERMAP_API_KEY", "")
OWM_BASE_URL: str = "https://api.openweathermap.org/data/2.5"

# ── ElevenLabs ────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")
ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# ── App / Railway ──────────────────────────────────────────────────────────────
# Railway injects $PORT automatically; fall back to 8000 for local dev
APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT: int = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# ── Cache ──────────────────────────────────────────────────────────────────────
WEATHER_CACHE_TTL: int = int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "300"))

# ── Rate limiting ──────────────────────────────────────────────────────────────
RATE_LIMIT_CHAT: str = os.getenv("RATE_LIMIT_CHAT", "20/minute")
RATE_LIMIT_VOICE: str = os.getenv("RATE_LIMIT_VOICE", "10/minute")
RATE_LIMIT_WEATHER: str = os.getenv("RATE_LIMIT_WEATHER", "30/minute")

# ── Demo mode: activates when any critical key is missing ──────────────────────
DEMO_MODE: bool = not all([GEMINI_API_KEY, OWM_API_KEY])


def api_status() -> dict:
    """Return which APIs are configured (without exposing key values)."""
    return {
        "gemini": bool(GEMINI_API_KEY),
        "openweathermap": bool(OWM_API_KEY),
        "elevenlabs": bool(ELEVENLABS_API_KEY),
        "demo_mode": DEMO_MODE,
    }
