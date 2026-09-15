# WeatherGPT 🌦️
### AI-Powered Multilingual Weather Intelligence
**Smart India Hackathon 2026 · Problem Statement SIH26068 · Ministry of Earth Sciences**

---

## What is WeatherGPT?

WeatherGPT is an AI-powered conversational weather platform that allows anyone — regardless of technical literacy — to ask natural-language questions about the weather in **English, हिन्दी, or తెలుగు** and receive accurate, actionable responses.

> "Will it rain in Visakhapatnam tomorrow?"  
> "రేపు విశాఖపట్నంలో వర్షం పడుతుందా?"  
> "क्या कल मुंबई में बारिश होगी?"

WeatherGPT combines **Google Gemini AI**, **OpenWeatherMap real-time data**, and **ElevenLabs voice synthesis** with a deterministic alert engine, decision-support advisories, and interactive maps.

---

## Features

| Feature | Status |
|---|---|
| 💬 Conversational AI (Gemini) | ✅ Implemented |
| 🌦️ Real-time Weather (OpenWeatherMap) | ✅ Implemented |
| 📅 5-Day Forecast | ✅ Implemented |
| 🚨 Extreme Weather Alert Engine | ✅ Implemented |
| 🌐 Multilingual — EN / HI / TE | ✅ Implemented |
| 🎤 Voice Input (SpeechRecognition) | ✅ Implemented |
| 🔊 Voice Output (ElevenLabs TTS) | ✅ Implemented |
| 🗺️ Interactive Map (Leaflet + OSM) | ✅ Implemented |
| 📊 Climate Analytics (Chart.js) | ✅ Implemented |
| 🌾 Decision Support (Farm/Aviation/Marine) | ✅ Implemented |
| 🚂 Railway Deployment Ready | ✅ Implemented |
| 🌐 GFS/WRF/NWP Architecture | ◐ Integration-ready |
| 📡 WIS2.0 / MQTT Integration | ◐ Integration-ready |

---

## Architecture

```
User (Text / Voice)
        │
        ▼
   WeatherGPT UI
  (HTML + JS + Tailwind)
        │
      HTTPS
        │
        ▼
   FastAPI Backend
        │
   ┌────┼────┐
   ▼    ▼    ▼
Gemini  OWM  ElevenLabs
  AI   Data    TTS
   │    │    │
   └────┼────┘
        ▼
  WeatherGPT Engine
        │
   ┌────┼────┐
   ▼    ▼    ▼
Alert Advisory Translation
Engine Engine  Layer
        │
        ▼
    Response
```

**Key principle**: All API keys live on the backend. The frontend never touches a secret.

---

## Setup

### Prerequisites
- Python 3.11+
- API Keys (see Environment Variables)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/weathergpt
cd weathergpt

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio API key |
| `GEMINI_MODEL` | Default: `gemini-3.6-flash` |
| `OPENWEATHERMAP_API_KEY` | OpenWeatherMap API key |
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | ElevenLabs voice ID (e.g. `EXAVITQu4vr4xnSDxMaL`) |

### Run locally

```bash
uvicorn main:app --reload
```

Open: **http://localhost:8000**

---

## 3–5 Minute SIH Presentation Demo Script

| Step | Action | Feature Highlight |
|---|---|---|
| **1** | Open WeatherGPT (`http://localhost:8000`) | Clean modern UI, real-time live hero weather card & GPS location |
| **2** | Ask: *"Will it rain in Visakhapatnam tomorrow?"* | Natural language parsing, real OpenWeatherMap forecast, 24h precipitation probability |
| **3** | Ask: *"Should I carry an umbrella?"* | Contextual AI reasoning grounded in real data |
| **4** | Switch Language to **తెలుగు** → Ask: *"రేపు వర్షం పడుతుందా?"* | Native Telugu script generation and accurate meteorological terminology |
| **5** | Click **🎤** Microphone | Browser Web Speech input (`te-IN`, `hi-IN`, `en-IN`) |
| **6** | Click **🔊 Listen** | Server-side ElevenLabs multilingual TTS synthesis (with browser fallback) |
| **7** | Switch to **🚨 Alerts** Tab | Deterministic weather risk rules (heavy rain, high wind, heatwave) with prototype disclaimers |
| **8** | Switch to **🌾 Advisories** Tab | Sector-specific decision support (Agriculture, Aviation METAR, Marine, Travel, Urban) |
| **9** | Switch to **📊 Climate** & **🗺️ Map** Tabs | Interactive Leaflet click-to-weather & Chart.js historical climate trends |
| **10** | Show **SIH Feature Coverage** & Architecture | GFS/WRF NWP readiness, WIS2.0/MQTT ingestion layer, and zero-leakage security model |

---

## Railway Deployment

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial WeatherGPT"
   git remote add origin https://github.com/YOUR_USERNAME/weathergpt
   git push -u origin main
   ```

2. **Create Railway project**
   - Go to [railway.app](https://railway.app)
   - New Project → Deploy from GitHub
   - Select your repository

3. **Add Environment Variables**
   - Railway dashboard → your service → Variables
   - Add all variables from `.env.example`
   - **Never** commit `.env` to GitHub

4. **Deploy**
   - Railway auto-deploys on every push
   - The `Dockerfile` handles port binding via `$PORT`

5. **Open**
   - Click the Railway public URL

---

## Tests

```bash
python -m pytest tests/ -v
```

---

## Demo Questions

| Language | Question |
|---|---|
| English | `Will it rain in Visakhapatnam tomorrow?` |
| English | `Give me an aviation weather briefing for Chennai` |
| Hindi | `क्या कल बारिश होगी?` |
| Telugu | `రేపు విశాఖపట్నంలో వర్షం పడుతుందా?` |
| English | `Is it suitable for farming tomorrow?` |
| English | `Is there any severe weather risk near me?` |

---

## Security

- ✅ All API keys server-side only
- ✅ `.env` in `.gitignore`
- ✅ Rate limiting on all endpoints
- ✅ Input validation (length limits, language validation)
- ✅ Graceful error handling (no stack traces to users)
- ✅ Demo mode when APIs unavailable

---

## SIH Problem Statement Coverage

**SIH26068 — Ministry of Earth Sciences**

> AI-powered conversational weather intelligence with real-time information, forecasts, warnings, climate analysis, and decision support through natural language, multilingual interaction and voice.

| Requirement | Implementation |
|---|---|
| Conversational AI | Google Gemini 2.0 Flash |
| Real-time weather | OpenWeatherMap API |
| Multilingual | EN / HI / TE with auto-detection |
| Voice input | Browser SpeechRecognition |
| Voice output | ElevenLabs multilingual TTS |
| Extreme weather alerts | Deterministic rule engine |
| Decision support | Agriculture / Aviation / Marine / Travel |
| Climate analysis | Chart.js trend visualization |
| GIS | Leaflet + OpenStreetMap |
| NWP (GFS/WRF) | Architecture ready |
| WIS2.0 / MQTT | Integration-ready abstraction |

---

*WeatherGPT — SIH 2026 Internal Prototype*  
*Not a production meteorological platform.*
