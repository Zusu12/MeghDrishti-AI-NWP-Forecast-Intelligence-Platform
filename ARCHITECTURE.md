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

### `alert_service.py` & `imd_service.py`
Dual-layer emergency alerting architecture:
1. **Official IMD / NDMA CAP Layer (`imd_service.py`)**:
   - 4-Color Coded District Weather Warnings (Green, Yellow, Orange, Red)
   - OASIS / ITU-T X.1303 CAP v1.2 JSON compliant warning documents
   - District & State mapping across Indian meteorological subdivisions
   - Official hazard categorization and emergency advisory instructions
2. **Deterministic Risk Engine (`alert_service.py`)**:
   - Thunderstorm detection (condition IDs 200–232)
   - Heavy rainfall (>7.6 mm/hr & >15 mm/3hr)
   - Extreme heat (>40°C / >44°C)
   - Extreme cold (<5°C / <1°C)
   - Strong winds (>50 km/h) & low visibility (<200m)
   - Real-time WebSocket push broadcasting

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
Operational Numerical Weather Prediction (NWP) model layer:
- **Active Operational**: OpenWeatherMap multi-model NWP assimilation (5-day / 3-hour cycle, 0.25° grid)
- **GFS layer**: NOAA Global Forecast System 0.25° grid via OWM assimilation pipeline
- **WRF layer**: Weather Research and Forecasting mesoscale model grid
- **ECMWF layer**: European Centre for Medium-Range Weather Forecasts IFS cycle integration
- Rich meteorological outputs: 2m Temperature, Dew Point, Surface & Sea Level Pressure, 10m Wind & Gusts, Relative Humidity, 3h Precipitation, Cloud Cover, POP
- SQLite TTL caching and deterministic offline demo fallback

### `ingestion_service.py`
Multi-protocol meteorological data ingestion architecture:
- **OpenWeatherMap REST API**: Operational global observational and NWP pipeline
- **MQTT IoT Sensor Grid**: Real-time pub/sub telemetry for Automatic Weather Stations (AWS)
- **WMO WIS2.0 Global Broker**: GeoJSON Notification Message (WNM) parser for WMO `in-imd`
- **WebSocket Push Stream**: Real-time push for early warning distribution

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
