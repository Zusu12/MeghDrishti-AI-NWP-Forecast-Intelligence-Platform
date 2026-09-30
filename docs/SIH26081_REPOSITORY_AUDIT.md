# SIH 2026 Problem Statement SIH26081: Comprehensive Repository Audit
## "Hybrid AI–NWP Multi-Model Forecast Blending System"

---

## 1. Executive Summary

- **Repository Original Identity:** WeatherGPT (A conversational weather chatbot with Gemini AI, ElevenLabs voice, OpenWeatherMap data, and sector advisories).
- **Target SIH 2026 Identity:** *Hybrid AI–NWP Multi-Model Forecast Blending System* — A scientific multi-model meteorological intelligence and operational blending platform.
- **Audit Goal:** Catalog all existing modules, evaluate reusable code, identify chatbot components to isolate or de-emphasize, and define the technical blueprint for the NWP ingestion, skill evaluation, adaptive weighting, multi-model consensus blending, and operational verification dashboard.

---

## 2. Comprehensive Component Audit Table

| Feature / Subsystem | Current Implementation | File Location | Action (REUSE / MODIFY / REMOVE / NEW) | Technical Reason & Migration Strategy |
|---|---|---|---|---|
| **FastAPI Core Application** | FastAPI instance with async lifespan, CORS middleware, SlowAPI rate-limiter, WebSocket connection manager, and static file serving. | `main.py` | **MODIFY** | **REUSE** the high-performance async server. **MODIFY** route mounting: add `/api/nwp/*`, `/api/workflow/*`, `/api/verification/*`. Isolate `/chat` and `/voice` so the platform works 100% without LLM/TTS dependencies. |
| **Configuration & Env** | Reads `.env` for keys (`OPENWEATHERMAP_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`), defines rate limits, timeouts, and cache TTLs. | `config.py` | **MODIFY** | **REUSE** robust env-loading. **MODIFY** to add NWP provider flags, operational schedule intervals, and default verification regions. Ensure zero startup crash if Gemini/ElevenLabs keys are missing. |
| **Database Persistence** | SQLite via `aiosqlite`. Tables: `conversations`, `query_history`, `weather_cache`. | `database.py` | **MODIFY** | **REUSE** async SQLite engine. **MODIFY** schema to support `forecast_models`, `forecast_data`, `observations`, `model_skill`, `model_weights`, `weather_regimes`, `blended_forecasts`, and `workflow_runs`. |
| **Observation / Ground Truth** | OpenWeatherMap 2.5 API integration with coordinate caching and city alias resolution. | `weather_service.py` | **REUSE** | **REUSE strictly as observational / reference ground truth**. Never misclassify OpenWeatherMap as an NWP model. |
| **NWP Model Ingestion** | Basic NWP classes (`GFSProvider`, `WRFProvider`, `ECMWFProvider`, `OpenWeatherMapNWPProvider`). | `nwp_service.py` | **MODIFY / EXTEND** | Refactor into a clean provider architecture (`nwp/providers/`). Support GFS (0.25°), WRF-ARW (mesoscale), ECMWF IFS, and a high-fidelity synthetic demo provider clearly tagged as `DEMO / SIMULATED DATA`. |
| **Forecast Data Standardization** | Ad-hoc dictionaries across OWM and demo models. | Distributed | **NEW** | Create standardized schema `StandardForecastPoint` in `schemas/forecast.py` (model_name, provider, coordinates, issue_time, valid_time, lead_time_hours, temperature, precipitation, PoP, wind speed/direction, pressure, humidity, weather_regime, metadata). |
| **Historical Model Skill Engine** | No historical verification engine; placeholder in `historical_service.py`. | `historical_service.py` | **NEW** | Build `ml/skill_verification.py`. Calculate continuous metrics (MAE, RMSE, Bias) and categorical contingency metrics (POD, FAR, CSI/Threat Score). Store in `model_skill` table. |
| **Weather Regime Detection** | Not implemented. | None | **NEW** | Build `ml/regime_detector.py` to classify conditions into `normal`, `monsoon`, `heavy_rainfall`, `convective`, `heatwave`, `dry_spell`, `high_wind`, and `storm/cyclone`. |
| **AI / Adaptive Model Weighting** | Hard-coded or simulated static values. | None | **NEW** | Build `ml/weighting_engine.py`. Dynamic weights $w_m \ge 0, \sum w_m = 1.0$ conditioned on historical skill, lead time, region, season, and weather regime. Baseline inverse-error weighting + ML meta-learner hooks. |
| **Consensus Forecast Blending** | Not implemented. | None | **NEW** | Build `ml/forecast_blender.py`. Weighted combination $\hat{Y} = \sum w_m Y_m$ for continuous variables and vector-averaged wind directions ($U, V$ components). |
| **Confidence & Disagreement Engine** | Not implemented. | None | **NEW** | Build `ml/confidence_engine.py`. Compute weighted variance/spread $\sigma$, inter-model range $\Delta$, and confidence score (HIGH, MEDIUM, LOW) with explainable reasons. |
| **Extreme Weather Risk Guidance** | Simple heuristic thresholds in `alert_service.py`. | `alert_service.py` | **MODIFY / EXTEND** | Enhance in `ml/extreme_detection.py` to evaluate blended forecasts against meteorological criteria (heavy rain >64.5mm/day, heatwaves, gale winds). Explicitly label as "Model-Based Guidance", separate from official IMD warnings. |
| **Official IMD / NDMA CAP Alerts** | CAP v1.2 JSON compliant 4-color coded district warning parser. | `imd_service.py` | **REUSE** | Retain as authoritative government warning feed, completely separate from AI model risk predictions. |
| **Model Weight Maps** | Not implemented. | None | **NEW** | Provide regional model weight distributions across India (North, South, East, West, Central, Coastal) with multi-variable/lead-time filtering for map visualization. |
| **Forecast Verification Dashboard** | Not implemented. | None | **NEW** | Add dedicated verification view comparing Individual Models (GFS, WRF) vs Blended Consensus with skill scores (MAE, RMSE, CSI) across regions and lead times. |
| **Operational Workflow & Scheduler** | Ad-hoc synchronous queries on client request. | None | **NEW** | Build `services/operational_workflow.py`. Support automated end-to-end execution: Ingest → Normalize → Skill Lookup → Regime Detect → Adaptive Weighting → Blend → Confidence → Extreme Detection → Storage. Provide manual trigger (`POST /api/workflow/run`) and background scheduler. |
| **Conversational Chat UI** | Large chat tab in HTML/JS. | `static/index.html`, `static/app.js` | **DE-EMPHASIZE / ISOLATE** | Remove chat as the primary view. The default landing page becomes the **Forecast Intelligence Dashboard**. Chat remains optional/isolated. |
| **Gemini AI Integration** | Two-phase LLM query parser and grounded weather explainer. | `gemini_service.py` | **ISOLATE** | Disconnect Gemini from the primary forecasting and blending pipeline. Keep code isolated as an optional explainer if `GEMINI_API_KEY` is present. Ensure zero hard dependencies. |
| **ElevenLabs Voice Integration** | Server-side multilingual TTS. | `elevenlabs_service.py` | **ISOLATE** | Disconnect from core workflow. Platform functions 100% without ElevenLabs. |
| **Frontend Dashboard UI** | HTML + CSS + Vanilla JS with 6 tabs (Chat, Forecast, Alerts, Climate, Map, Advisories). | `static/index.html`, `static/styles.css`, `static/app.js` | **MODIFY** | Transform navigation into professional meteorological dashboard: **Dashboard**, **Forecast**, **Model Comparison**, **Weight Maps**, **Verification**, **Extreme Weather**, **Operational Workflow**, **Map**. |
| **Interactive Map** | Leaflet.js with OSM base tiles. | `static/app.js` | **MODIFY / EXTEND** | Add layers for Observation, GFS, WRF, Blended Forecast, Model Weight Distribution, and Extreme Risk Polygons. |
| **Deployment Configurations** | `Dockerfile`, `railway.json`, `Procfile`. | Root | **REUSE** | Keep Railway, Docker, and PaaS compatibility. |
| **Test Suite** | 55 unit and integration tests passing. | `tests/` | **EXTEND** | Add automated test suites for normalization, weight normalization ($\sum w = 1.0$), consensus blending, vector wind averaging, verification metrics (CSI, POD, FAR, MAE), and operational pipeline execution. |

---

## 3. Technology Stack & Dependencies

- **Language & Runtime:** Python 3.14 (Virtual Environment in `./venv/`).
- **Web Framework:** FastAPI + Uvicorn + Pydantic v2.
- **Data & Scientific:** Pure-Python vectorized math, NumPy / SciPy compatibility, SQLite (`aiosqlite`).
- **Frontend:** Vanilla HTML5, Modern CSS (Glassmorphic / Dark / Clean Meteorological Palette), Leaflet.js (maps), Chart.js (verification and comparison graphs). Zero external frontend build tool required; fast local and remote execution.
- **Testing:** `pytest` + `anyio` + `starlette.testclient`. All 55 baseline tests verified passing.
