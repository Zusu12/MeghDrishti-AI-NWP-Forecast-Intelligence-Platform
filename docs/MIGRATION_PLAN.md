# MeghDrishti — Technical Migration Plan
## SIH 2026 Problem Statement SIH26081: AI–NWP Forecast Intelligence Platform

---

## 1. Migration Scope & Inventory

### 1.1. REUSED Components (Preserve & Protect Working Features)

| Component | File / Service | Role in Hybrid AI–NWP Architecture | Preservation Rule |
|---|---|---|---|
| **FastAPI Backend** | `main.py` | Primary API host, routing, lifespan, CORS, rate-limiting, static file serving | Do NOT rebuild. Add new routes under `/api/nwp/*` and `/api/blending/*`. |
| **WeatherGPT UI** | `static/index.html`, `static/styles.css`, `static/app.js` | Core user interface, tabs, responsive mobile/desktop layout | Preserve existing theme, tabs, chat, and branding. Add NWP Intelligence panel. |
| **OpenWeatherMap Integration** | `weather_service.py` | **Observation / Ground Truth / Current Weather Reference** | Strictly separate from NWP models. Keep city aliases, caching, and coordinate lookup. |
| **Gemini AI Integration** | `gemini_service.py` | **Grounded Conversational Explanation & Intent Parsing** | Feed structured blended forecast JSON to Gemini. Enforce strict rule: Gemini never invents numbers. |
| **IMD / NDMA CAP Engine** | `imd_service.py` | Official 4-color coded district alerts (CAP v1.2 compliant) | Keep distinct from model-derived risk alerts. |
| **Real-time Alert Engine** | `alert_service.py` | Deterministic risk rules (heatwave, cold, rain, wind) | Enhance to accept blended forecast timesteps in addition to raw weather. |
| **Sector Advisories** | `advisory_service.py` | Agriculture, Aviation, Marine, Travel, Urban decision support | Connect to blended forecast data for more accurate agronomic & marine guidance. |
| **Voice & ElevenLabs** | `elevenlabs_service.py` | Multilingual TTS (English, Hindi, Telugu) | Keep server-side synthesis and browser SpeechSynthesis fallback. |
| **Translation Engine** | `translation_service.py` | Script-based language detection and pivoting | Preserve Unicode detection and language routing. |
| **IoT / WIS2.0 Ingestion** | `ingestion_service.py` | MQTT sensor grid and WMO WIS2.0 Global Broker WNM | Maintain real-time telemetry streaming. |
| **Database Persistence** | `database.py` | SQLite (`aiosqlite`) conversations, cache, query history | Extend schema to store NWP model metadata, skill scores, and blended runs. |
| **Deployment Configurations**| `Dockerfile`, `railway.json`, `Procfile` | Containerization and cloud deployment | Maintain current Docker and Railway compatibility. |

---

### 1.2. NEW Components to Implement

| Subsystem | New Files / Modules | Core Functionality |
|---|---|---|
| **NWP Model Ingestion** | `nwp/providers/base.py`<br>`nwp/providers/gfs.py`<br>`nwp/providers/wrf.py`<br>`nwp/providers/ecmwf.py`<br>`nwp/providers/demo.py` | Clean provider abstraction with standardized interfaces for NOAA GFS, WRF-ARW, ECMWF IFS, and demo provider with explicit labeling. |
| **Data Normalization** | `nwp/normalization.py` | Schema standardization, unit conversions, missing variable imputation, coordinate grid alignment, and logging. |
| **Forecast Verification & Skill** | `nwp/verification.py`<br>`models/skill.py` | Historical verification engine calculating MAE, RMSE, Bias, CSI, POD, FAR against observations; model skill database. |
| **AI / Adaptive Model Weighting** | `ml/weighting/engine.py`<br>`ml/weighting/baseline.py`<br>`ml/weighting/regime.py` | Dynamic weighting engine factoring in lead time, region, season, weather regime, and historical skill. Non-negative weights summing to 1.0. |
| **Multi-Model Forecast Blender** | `ml/blending/blender.py` | Vectorized blending for temperature, precipitation, wind speed, pressure, humidity, and precipitation probability. |
| **Confidence & Disagreement** | `ml/blending/confidence.py` | Model agreement calculation, weighted variance/spread, inter-model range, confidence scoring (LOW/MEDIUM/HIGH) with transparent formulas. |
| **Extreme Weather Alerts** | `ml/blending/extreme_detection.py` | Configurable meteorological threshold detection on blended forecast (heavy rain, heatwave, gale wind). Demarcated from official warnings. |
| **Grounded Gemini Explainer** | `services/nwp_explanation_service.py` | Prepares structured JSON with blended forecast, weights, confidence, and disagreement for natural-language synthesis. |
| **NWP Intelligence Dashboard** | `static/index.html` (NWP section)<br>`static/app.js` (NWP renderer) | Interactive model comparison, dynamic weight bars, confidence gauge, disagreement indicators, and forecast timeline. |
| **Multi-Model Map Layers** | `static/app.js` (Leaflet layers) | Layer toggles for observation, GFS, WRF, ECMWF, blended forecast, and alert polygons. |

---

## 2. Phased Implementation Roadmap

### Phase 1: Architecture, Contracts & Ingestion Abstraction
- Finalize `docs/ARCHITECTURE.md` and `docs/MIGRATION_PLAN.md`.
- Establish standardized forecast data schemas (`schemas/forecast.py`, `schemas/nwp.py`, `schemas/blending.py`).
- Implement `NWPProvider` abstraction in `nwp_service.py` / modular provider structure.
- Add high-fidelity demo generator clearly marked with `"DEMO / SIMULATED NWP DATA"`.

### Phase 2: NWP Ingestion, Normalization & Observation Separation
- Standardize all model outputs into internal schema:
  - Temperature: $^\circ\text{C}$
  - Precipitation: $\text{mm}$ (accumulated over interval)
  - Wind speed: $\text{km/h}$ (and $\text{m/s}$)
  - Pressure: $\text{hPa}$
  - Relative Humidity: $\%$
- Keep OpenWeatherMap strictly in `weather_service.py` as observation/ground-truth.
- Add normalization tests and validation checks.

### Phase 3: Historical Model Skill & Verification Engine
- Implement verification metrics: MAE, RMSE, Mean Bias Error (MBE).
- For precipitation events: Probability of Detection (POD), False Alarm Ratio (FAR), Critical Success Index (CSI).
- Create `ModelSkill` records in database partitioned by `(model, region, season, variable, lead_time, weather_regime)`.
- Fallback baseline skill table when historical observations are sparse.

### Phase 4: Weather Regime Detection & Adaptive AI Weighting
- Implement regime detector: `normal`, `heavy_rainfall`, `convective`, `heatwave`, `cyclone_wind`, `monsoon`.
- Implement dynamic weighting engine:
  - $w_m \ge 0$, $\sum w_m = 1.0$.
  - Dependent on lead time $\tau$, regime $R$, region, and historical skill.
  - Explainable weighting factors exposed in API response.
  - Extension point for machine learning regression / meta-learning.

### Phase 5: Forecast Blending, Confidence & Disagreement Engine
- Implement multi-model blending: $\hat{Y} = \sum w_m Y_m$.
- Compute model spread: $\sigma = \sqrt{\sum w_m (Y_m - \hat{Y})^2}$, inter-model range: $\max(Y_m) - \min(Y_m)$.
- Compute confidence score $C \in [0, 100]\%$ and categorical rating (**HIGH**, **MEDIUM**, **LOW**).
- Generate human-readable reasons for confidence.

### Phase 6: Extreme Weather Detection & Grounded Gemini Integration
- Meteorological threshold evaluator for blended forecast.
- Clear separation between Model-Based Alerts and Official IMD Warnings.
- Grounded Gemini explanation pipeline passing structured meteorological JSON.
- Enhance Chat endpoint so user queries ("Why is rain expected?", "Compare GFS and WRF") query blended data.

### Phase 7: NWP Intelligence Dashboard & Map Layer Enhancements
- Build "NWP Intelligence" view in the frontend.
- Display:
  - Current observation (OpenWeather)
  - Side-by-side model comparison (GFS, WRF, ECMWF)
  - Dynamic weight breakdown
  - Blended forecast summary
  - Confidence rating & disagreement spread
  - 120-hour timeline
- Add Leaflet map layer switcher for observation vs blended forecast.

### Phase 8: Verification, Test Suite & Documentation
- Comprehensive automated test suite (`pytest`) covering:
  - Normalization & unit conversions
  - Weight normalization ($\sum w = 1.0$)
  - Blending calculation correctness
  - Confidence & disagreement formulas
  - Extreme weather detection rules
  - Grounding prompt formatting
- Generate `/reports/model_evaluation.md` and update `README.md`.

---

## 3. Mathematical Formulations

### 3.1. Dynamic Model Weighting Formula
For a given variable $v$ (e.g. temperature, precipitation) at lead time $\tau$:
$$s_m(v, \tau, R) = \frac{1}{\text{MAE}_m(v, \tau, R) + \epsilon} \cdot \alpha_m(\tau)$$
where:
- $\text{MAE}_m$ is the historical mean absolute error for model $m$ in regime $R$ at lead time $\tau$.
- $\epsilon = 0.01$ prevents division by zero.
- $\alpha_m(\tau)$ is a lead-time reliability weighting factor.
Normalized weight:
$$w_m(v, \tau) = \frac{s_m(v, \tau, R)}{\sum_{k=1}^M s_k(v, \tau, R)}$$

### 3.2. Blended Forecast Formulation
For continuous variables (temperature, wind, pressure, humidity, rainfall amount):
$$\hat{Y}_{v, \tau} = \sum_{m=1}^M w_m(v, \tau) \cdot Y_{m, v, \tau}$$
For precipitation probability ($PoP$):
$$\widehat{PoP}_{\tau} = \sum_{m=1}^M w_m(\text{precip}, \tau) \cdot PoP_{m, \tau}$$

### 3.3. Model Disagreement (Spread)
$$\sigma_{v, \tau} = \sqrt{\sum_{m=1}^M w_m(v, \tau) \cdot (Y_{m, v, \tau} - \hat{Y}_{v, \tau})^2}$$
Inter-model range:
$$\Delta_{v, \tau} = \max_{m}(Y_{m, v, \tau}) - \min_{m}(Y_{m, v, \tau})$$

### 3.4. Forecast Confidence Score
$$C = 100 \times \max\left(0, \min\left(1, 0.40 \cdot S_{\text{agreement}} + 0.30 \cdot S_{\text{skill}} + 0.20 \cdot S_{\text{coverage}} - 0.10 \cdot P_{\text{leadtime}}\right)\right)$$
where:
- $S_{\text{agreement}} = 1 - \min\left(1, \frac{\sigma}{\sigma_{\text{threshold}}}\right)$
- $S_{\text{skill}} = 1 - \min\left(1, \frac{\sum w_m \text{MAE}_m}{\text{MAE}_{\text{baseline}}}\right)$
- $S_{\text{coverage}} = \frac{M_{\text{available}}}{M_{\text{total}}}$
- $P_{\text{leadtime}} = \frac{\tau}{\tau_{\max}}$

---

## 4. API Endpoints Specification

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/weather/current` | Current observational weather from OpenWeatherMap |
| `GET` | `/api/weather/forecast` | Standard multi-day forecast |
| `GET` | `/api/nwp/models` | List available NWP models & capabilities |
| `GET` | `/api/nwp/forecast` | Raw/normalized forecast from a specific NWP model |
| `GET` | `/api/nwp/compare` | Multi-model comparison across GFS, WRF, ECMWF |
| `GET` | `/api/nwp/blended` | Complete AI-blended forecast with weights & confidence |
| `GET` | `/api/nwp/weights` | Dynamic model weights breakdown for a location |
| `GET` | `/api/nwp/confidence`| Confidence score, disagreement metrics, and rationale |
| `GET` | `/api/nwp/skill` | Historical model skill metrics (MAE, RMSE, Bias) |
| `POST` | `/api/nwp/blend` | On-demand forecast blending for custom coordinates |
| `POST` | `/api/chat` | Conversational query grounded in blended forecast |
| `GET` | `/alerts/official` | Authoritative IMD / NDMA CAP v1.2 district warnings |
