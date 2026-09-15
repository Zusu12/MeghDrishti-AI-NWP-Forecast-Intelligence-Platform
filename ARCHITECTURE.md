# WeatherGPT Architecture

## System Overview

WeatherGPT is a modular, service-oriented weather intelligence platform.

```
                       USER
                        │
             ┌──────────▼──────────┐
             │    WeatherGPT UI    │
             │  HTML + JS + Tailwind│
             │  Leaflet · Chart.js  │
             └──────────┬──────────┘
                        │ HTTPS
                        │
             ┌──────────▼──────────┐
             │    FastAPI Backend   │
             │   main.py + uvicorn  │
             │   Rate limiting      │
             │   WebSocket alerts   │
             └──┬───────┬───────┬──┘
                │       │       │
        ┌───────▼─┐  ┌──▼───┐  ┌▼────────┐
        │  Gemini  │  │ OWM  │  │ElevenLabs│
        │  AI API  │  │ API  │  │  TTS API │
        └───────┬──┘  └──┬───┘  └──────────┘
                │         │
                └────┬────┘
                     │
          ┌──────────▼──────────┐
          │   WeatherGPT Engine  │
          │  gemini_service.py   │
          │  weather_service.py  │
          └──┬──────┬──────┬────┘
             │      │      │
      ┌──────▼─┐  ┌─▼────┐  ┌▼──────────┐
      │ Alert  │  │Advis.│  │Translation │
      │ Engine │  │Engine│  │  Service   │
      └────────┘  └──────┘  └───────────┘
             │
      ┌──────▼──────┐
      │   SQLite DB  │
      │(conversations│
      │ cache/history│
      └─────────────┘
```

---

## Module Descriptions

### `main.py`
FastAPI application. Handles all HTTP and WebSocket routes. Assembles the pipeline: intent → weather → alerts → Gemini response → translation. Rate-limits all endpoints.

### `config.py`
Single source of truth for all environment variables. Detects demo mode. Railway `$PORT` compatible.

### `gemini_service.py`
Two-phase Gemini interaction:
1. **Intent parsing** — extract location, date, variable, query type
2. **Response generation** — uses *only* injected weather data (never invents values)

### `weather_service.py`
OpenWeatherMap integration with:
- TTL-based SQLite caching
- City alias resolution (Vizag, Bombay, etc.)
- Graceful demo fallback

### `alert_service.py`
Deterministic rule-based engine. Evaluates:
- Thunderstorm (condition ID range 200–232)
- Heavy rainfall (>7.6 mm/hr)
- Extreme heat (>42°C)
- Extreme cold (<5°C)
- Strong winds (>50 km/h)
- Poor visibility (<200m)

All output carries mandatory prototype disclaimer.

### `elevenlabs_service.py`
Server-side ElevenLabs TTS. API key never reaches frontend. Uses `eleven_multilingual_v2` for Hindi/Telugu support. Falls back silently.

### `translation_service.py`
Script-based language detection (Unicode ranges for Hindi/Telugu). Uses `deep-translator` for translation. English used as processing pivot language.

### `advisory_service.py`
Sector-specific decision support:
- Agriculture, Aviation, Marine, Travel, Outdoor, Urban
- Real weather data injected into sector-specific Gemini prompts
- All output labelled as prototype guidance

### `historical_service.py`
Interface for historical climate data. Currently returns **clearly-labelled demo data**. Designed for ERA5/IMD dataset integration.

### `nwp_service.py`
Provider abstraction for NWP models:
- GFS stub (NOAA NOMADS integration point)
- WRF stub (WRF-ARW server integration point)
- All output labelled as prototype

### `ingestion_service.py`
Unified data ingestion layer:
- **Active**: OpenWeatherMap REST API
- **Integration-ready**: WebSocket, MQTT, WIS2.0

### `database.py`
SQLite via `aiosqlite`. Tables: conversations, query_history, weather_cache.
Designed for PostgreSQL/MongoDB migration.

---

## Future Production Architecture

```
                     WeatherGPT
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   OpenWeather       GFS / WRF       Official APIs
     (active)     (integration-ready)    │
        │                │           IMD / NDMA
        └────────────────┼───────────────┘
                         ▼
                  Unified Weather Layer
                         │
                   Alert Engine
                         │
                   Advisory Engine
                         │
                   Gemini AI Layer
                         │
                   Multilingual TTS
                         │
                    User Response
```

---

## Data Flow — Chat Request

```
User: "Will it rain in Vizag tomorrow?"
  │
  ▼ POST /chat
FastAPI receives → validates input
  │
  ▼ translation_service
Detect language (en/hi/te) → translate to English if needed
  │
  ▼ gemini_service.parse_intent()
{location: "Visakhapatnam", date: "tomorrow", variable: "rain", type: "forecast"}
  │
  ▼ weather_service.get_current_weather() + get_forecast()
Real OWM data retrieved (or demo data in demo mode)
  │
  ▼ alert_service.check_alerts()
Deterministic risk evaluation
  │
  ▼ gemini_service.generate_response()
Gemini writes response using ONLY the injected weather data
  │
  ▼ translation_service.translate_from_english()
Response translated to user's language
  │
  ▼ User receives response + weather card + alerts
```

---

## Security Model

| Layer | Measure |
|---|---|
| Frontend | No API keys. All calls → FastAPI backend |
| Backend | Rate limiting per IP (slowapi) |
| Secrets | Environment variables only |
| Git | `.env` in `.gitignore` |
| Input | Pydantic validation, length limits |
| Errors | Never expose stack traces |
| TTS | ElevenLabs called server-side |

---

## Deployment — Railway

Railway reads `Dockerfile`. Port is set via `$PORT` environment variable.

```
GitHub push
    ↓
Railway auto-build (Dockerfile)
    ↓
uvicorn main:app --host 0.0.0.0 --port $PORT
    ↓
WeatherGPT live at Railway URL
```

*SIH 2026 Internal Prototype — Not for production use.*
