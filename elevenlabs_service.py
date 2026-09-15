"""
elevenlabs_service.py — ElevenLabs TTS integration with high-clarity voice settings.
All ElevenLabs API calls happen server-side. API key never reaches the frontend.
Cleans markdown, expands abbreviations, and converts Telugu script into accurate
phonetic Romanized syllables for smooth, articulate pronunciation.
"""
import logging
import re
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Telugu Unicode to Phonetic Latin mappings
TELUGU_VOWELS = {
    '\u0C05': 'a', '\u0C06': 'aa', '\u0C07': 'i', '\u0C08': 'ee',
    '\u0C09': 'u', '\u0C0A': 'oo', '\u0C0B': 'ru', '\u0C60': 'roo',
    '\u0C0C': 'lu', '\u0C61': 'loo',
    '\u0C0E': 'e', '\u0C0F': 'ae', '\u0C10': 'ai',
    '\u0C12': 'o', '\u0C13': 'o', '\u0C14': 'au',
}

TELUGU_VOWEL_SIGNS = {
    '\u0C3E': 'aa', '\u0C3F': 'i', '\u0C40': 'ee',
    '\u0C41': 'u', '\u0C42': 'oo', '\u0C43': 'ru', '\u0C44': 'roo',
    '\u0C46': 'e', '\u0C47': 'ae', '\u0C48': 'ai',
    '\u0C4A': 'o', '\u0C4B': 'o', '\u0C4C': 'au',
}

TELUGU_VIRAMA = '\u0C4D'    # ్ (halant)
TELUGU_ANUSVARA = '\u0C02'  # ం (m / n)
TELUGU_VISARGA = '\u0C03'   # ః (h)

TELUGU_CONSONANTS = {
    '\u0C15': 'ka', '\u0C16': 'kha', '\u0C17': 'ga', '\u0C18': 'gha', '\u0C19': 'nga',
    '\u0C1A': 'cha', '\u0C1B': 'chha', '\u0C1C': 'ja', '\u0C1D': 'jha', '\u0C1E': 'nya',
    '\u0C1F': 'ta', '\u0C20': 'tha', '\u0C21': 'da', '\u0C22': 'dha', '\u0C23': 'na',
    '\u0C24': 'tha', '\u0C25': 'thha', '\u0C26': 'dha', '\u0C27': 'dhha', '\u0C28': 'na',
    '\u0C2A': 'pa', '\u0C2B': 'pha', '\u0C2C': 'ba', '\u0C2D': 'bha', '\u0C2E': 'ma',
    '\u0C2F': 'ya', '\u0C30': 'ra', '\u0C31': 'ra',
    '\u0C32': 'la', '\u0C33': 'la', '\u0C35': 'va',
    '\u0C36': 'sha', '\u0C37': 'sha', '\u0C38': 'sa', '\u0C39': 'ha',
}

TELUGU_COMMON_WORDS = {
    "విశాఖపట్నంలో": "Vishaakhapatnam lo",
    "విశాఖపట్నం": "Vishaakhapatnam",
    "ప్రస్తుత": "prasthutha",
    "వాతావరణం": "vaathaavaranam",
    "నిర్మలంగా": "nirmalamgaa",
    "ఉంది": "vundi",
    "ఉష్ణోగ్రత": "ushnogratha",
    "తేమ": "thaema",
    "గాలి": "gaali",
    "వేగం": "vaegam",
    "వర్షం": "varsham",
    "పడుతుందా": "paduthundaa",
    "అవకాశం": "avakaasham",
    "గొడుగు": "godugu",
    "రాబోయే": "raaboyae",
    "గంటల్లో": "gantallo",
    "సెల్సియస్": "Celsius",
    "శాతం": "percent",
    "డిగ్రీల": "digreela",
    "డిగ్రీలు": "digreelu",
}


def _telugu_to_roman(text: str) -> str:
    """Convert Telugu script into phonetic Latin syllables for clear TTS pronunciation."""
    for word, roman in TELUGU_COMMON_WORDS.items():
        text = text.replace(word, roman)

    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in TELUGU_VOWELS:
            out.append(TELUGU_VOWELS[c])
            i += 1
        elif c in TELUGU_CONSONANTS:
            base = TELUGU_CONSONANTS[c][:-1]
            if i + 1 < n:
                next_c = text[i + 1]
                if next_c == TELUGU_VIRAMA:
                    out.append(base)
                    i += 2
                elif next_c in TELUGU_VOWEL_SIGNS:
                    out.append(base + TELUGU_VOWEL_SIGNS[next_c])
                    i += 2
                elif next_c == TELUGU_ANUSVARA:
                    out.append(base + 'am')
                    i += 2
                elif next_c == TELUGU_VISARGA:
                    out.append(base + 'aha')
                    i += 2
                else:
                    out.append(base + 'a')
                    i += 1
            else:
                out.append(base + 'a')
                i += 1
        elif c == TELUGU_ANUSVARA:
            out.append('m')
            i += 1
        elif c == TELUGU_VISARGA:
            out.append('h')
            i += 1
        elif c in TELUGU_VOWEL_SIGNS:
            out.append(TELUGU_VOWEL_SIGNS[c])
            i += 1
        elif c == TELUGU_VIRAMA:
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _get_client():
    """Initialise ElevenLabs client."""
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not configured.")
    from elevenlabs.client import ElevenLabs
    return ElevenLabs(api_key=config.ELEVENLABS_API_KEY)


def _clean_text_for_speech(text: str, language: str = "en") -> str:
    """
    Remove formatting symbols, emojis, and expand abbreviations
    so the TTS model pronounces text naturally and smoothly.
    """
    # 1. Remove markdown bold, italic, headers, backticks, bullet dashes
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"^\s*[-*•]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)

    # 2. Expand weather units into natural spoken words
    if language == "en":
        text = re.sub(r"(\d+(?:\.\d+)?)\s*°\s*C\b", r"\1 degrees Celsius", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*°\b", r"\1 degrees", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*km/h\b", r"\1 kilometers per hour", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*mm/hr\b", r"\1 millimeters per hour", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*mm\b", r"\1 millimeters", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", text)
        text = re.sub(r"\bPoP\b", "probability of precipitation", text, flags=re.IGNORECASE)
        text = re.sub(r"\bhPa\b", "hectopascals", text)
        text = re.sub(r"\bvis\b", "visibility", text, flags=re.IGNORECASE)
    elif language == "hi":
        text = re.sub(r"(\d+(?:\.\d+)?)\s*°\s*C\b", r"\1 डिग्री सेल्सियस", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*°\b", r"\1 डिग्री", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 प्रतिशत", text)
        text = re.sub(r"किमी/घंटा\b", "किलोमीटर प्रति घंटा", text)
        text = re.sub(r"km/h\b", "किलोमीटर प्रति घंटा", text)
    elif language == "te":
        # Expand abbreviations and symbols directly into authentic Telugu speech words
        text = re.sub(r"(\d+(?:\.\d+)?)\s*°\s*C\b", r"\1 డిగ్రీల సెల్సియస్", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*°\b", r"\1 డిగ్రీలు", text)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 శాతం", text)
        text = re.sub(r"కి\.మీ/గం\b", "కిలోమీటర్లు ప్రతి గంటకు", text)
        text = re.sub(r"km/h\b", "కిలోమీటర్లు ప్రతి గంటకు", text)
        text = re.sub(r"mm\b", "మిల్లీమీటర్లు", text)
        # Keep pure Telugu Unicode script; eleven_v3 natively understands Telugu phonology and conjuncts!

    # 3. Strip emojis that confuse the acoustic speech model
    emoji_pattern = re.compile(
        "[\U0001F1E0-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF\U0000FE00-\U0000FE0F]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)

    # 4. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def text_to_speech(text: str, language: str = "en") -> bytes:
    """
    Convert text to speech using ElevenLabs API with high clarity broadcast settings.

    Args:
        text:     Text to synthesise.
        language: Language code ('en', 'hi', 'te').

    Returns:
        Raw MP3 audio bytes.

    Raises:
        RuntimeError: If ElevenLabs is unavailable or API call fails.
    """
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ElevenLabs API key not configured.")

    clean_text = _clean_text_for_speech(text, language)

    # Truncate very long texts to avoid quota exhaustion
    max_chars = 450
    if len(clean_text) > max_chars:
        clean_text = clean_text[:max_chars].rsplit(" ", 1)[0] + "."
        logger.warning(f"TTS text truncated to {max_chars} characters.")

    try:
        client = _get_client()
        from elevenlabs import VoiceSettings

        # Optimized broadcast settings:
        # For Telugu, eleven_v3 requires stability around 0.6 for natural melodic flow
        stability_val = 0.60 if language == "te" else 0.75
        settings = VoiceSettings(
            stability=stability_val,
            similarity_boost=0.82,
            style=0.0,
            use_speaker_boost=True,
        )

        # For Telugu, eleven_v3 natively supports Telugu with articulate phonetics
        model = "eleven_v3" if language == "te" else config.ELEVENLABS_MODEL
        voice_id = config.ELEVENLABS_VOICE_ID  # default: onwK4e9ZLuTAKqWW03F9 (Daniel)

        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=clean_text,
            model_id=model,
            voice_settings=settings,
            output_format="mp3_44100_128",
        )

        audio_bytes = b"".join(audio_generator)
        logger.info(f"ElevenLabs TTS: generated {len(audio_bytes)} bytes for lang={language} using voice={voice_id}")
        return audio_bytes

    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")
        raise RuntimeError(f"Voice generation failed: {str(e)}")


def is_configured() -> bool:
    """Return True if ElevenLabs is properly configured."""
    return bool(config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID)
