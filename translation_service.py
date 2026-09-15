"""
translation_service.py — Multilingual support for English, Hindi, and Telugu.
Includes Unicode script detection, in-memory caching, offline dictionary fallbacks,
and graceful deep-translator error handling.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "speech_code": "en-IN", "label": "EN"},
    "hi": {"name": "Hindi",   "speech_code": "hi-IN", "label": "हि"},
    "te": {"name": "Telugu",  "speech_code": "te-IN", "label": "తె"},
}

HINDI_RANGE  = re.compile(r"[\u0900-\u097F]")
TELUGU_RANGE = re.compile(r"[\u0C00-\u0C7F]")

_cache: dict[str, str] = {}

# Offline phrase mappings for guaranteed resilience
OFFLINE_PHRASES_TO_EN = {
    "क्या कल बारिश होगी?": "Will it rain tomorrow?",
    "आज का तापमान क्या है?": "What is the temperature today?",
    "कोई मौसम चेतावनी है?": "Is there any severe weather risk?",
    "क्या कल खेती के लिए अच्छा है?": "Is it suitable for farming tomorrow?",
    "विमानन मौसम जानकारी दें": "Give me an aviation weather briefing",
    "समुद्री यात्रा के लिए मौसम?": "Is it safe for marine activities?",
    "రేపు వర్షం పడుతుందా?": "Will it rain tomorrow?",
    "నేడు ఉష్ణోగ్రత ఎంత?": "What is the temperature today?",
    "తీవ్రమైన వాతావరణ హెచ్చరికలు ఉన్నాయా?": "Is there any severe weather risk?",
    "రేపు వ్యవసాయానికి అనుకూలంగా ఉంటుందా?": "Is it suitable for farming tomorrow?",
    "విమానయాన వాతావరణ సారాంశం ఇవ్వండి": "Give me an aviation weather briefing",
    "సముద్ర యాత్రకు వాతావరణం అనుకూలంగా ఉందా?": "Is it safe for marine activities?",
    "రేపు విశాఖపట్నంలో వర్షం పడుతుందా?": "Will it rain in Visakhapatnam tomorrow?",
    "कल मुंबई में मौसम कैसा होगा?": "How will the weather be in Mumbai tomorrow?",
}


def detect_language(text: str) -> str:
    """Detect language based on Unicode character script inspection."""
    if TELUGU_RANGE.search(text):
        return "te"
    if HINDI_RANGE.search(text):
        return "hi"
    return "en"


def translate_to_english(text: str, source_lang: str) -> str:
    """Translate incoming user query to English for unified intent processing."""
    clean = text.strip()
    if source_lang == "en" or not clean:
        return clean

    # Check offline dictionary first
    if clean in OFFLINE_PHRASES_TO_EN:
        return OFFLINE_PHRASES_TO_EN[clean]

    cache_key = f"{source_lang}:en:{clean}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source=source_lang, target="en").translate(clean)
        _cache[cache_key] = translated
        logger.info(f"Translated [{source_lang}→en]: {clean[:40]!r} -> {translated[:40]!r}")
        return translated
    except Exception as e:
        logger.warning(f"Translation to English unavailable: {e}. Using raw query.")
        return clean


def translate_from_english(text: str, target_lang: str) -> str:
    """Translate English response into target language (Hindi or Telugu)."""
    clean = text.strip()
    if target_lang == "en" or not clean:
        return clean

    cache_key = f"en:{target_lang}:{clean[:100]}"
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        from deep_translator import GoogleTranslator
        translated = GoogleTranslator(source="en", target=target_lang).translate(clean)
        _cache[cache_key] = translated
        logger.info(f"Translated [en→{target_lang}]: {clean[:40]!r}")
        return translated
    except Exception as e:
        logger.warning(f"Translation to {target_lang} unavailable: {e}")
        return clean


def get_speech_code(lang: str) -> str:
    return SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["en"])["speech_code"]
