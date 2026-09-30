# WeatherGPT — Hybrid AI–NWP Multi-Model Forecast Intelligence
## System Architecture Specification (SIH 2026 Problem Statement: SIH26081)

---

## 1. Executive Summary

**Problem Statement (SIH26081):** "Hybrid AI–NWP Multi-Model Forecast Blending System"  
**Platform Identity:** *WeatherGPT — Hybrid AI–NWP Multi-Model Forecast Intelligence*

WeatherGPT transforms from a conversational weather assistant into a scientific multi-model meteorological intelligence platform. The core is an AI-assisted Numerical Weather Prediction (NWP) multi-model forecast blending engine that ingests heterogeneous model forecasts (NOAA GFS, WRF-ARW, ECMWF IFS, Bharat Forecast System), normalizes their spatiotemporal grids, evaluates historical model skill, dynamically computes optimal model weights conditioned on lead time, region, and weather regime, blends the predictions, quantifies forecast confidence and model disagreement, detects extreme weather risks, and exposes actionable insights through the conversational WeatherGPT interface powered by grounded Google Gemini AI and ElevenLabs voice synthesis.

---

## 2. High-Level System Architecture

```
                  RAW NWP / OBSERVATION SOURCES
                               │
       ┌───────────────┬───────┴───────┬───────────────┐
       ▼               ▼               ▼               ▼
   NOAA GFS         WRF-ARW        ECMWF IFS    OWM (Observation)
   (0.25° Grid)   (Mesoscale)     (0.1° / 9km)   (Ground Truth/Ref)
       │               │               │               │
       └───────────────┼───────────────┘               │
                       ▼                               │
             DATA NORMALIZATION LAYER                  │
         (Standardized Gridded Forecast)               │
                       │                               │
                       ├───────────────────────────────┘
                       ▼
            HISTORICAL MODEL SKILL &
              VERIFICATION ENGINE
          (MAE, RMSE, Bias, CSI, POD)
                       │
                       ▼
             WEATHER REGIME DETECTION
        (Normal, Convective, Monsoon, Heatwave)
                       │
                       ▼
           AI / ADAPTIVE WEIGHTING ENGINE
          (Dynamic Weights: w_m >= 0, Σw_m = 1)
                       │
                       ▼
            MULTI-MODEL FORECAST BLENDER
       (Blended = Σ [Weight_m × ModelForecast_m])
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
     Blended        Extreme         Model
    Forecast      Weather Risk   Disagreement
   (T, P, W, H)   (Thresholds)   & Confidence
        │              │              │
        └──────────────┼──────────────┘
                       ▼
          STRUCTURED METEOROLOGICAL JSON
                       │
                       ▼
           GEMINI EXPLANATION ENGINE
          (Grounded Prompts — No Hallucinations)
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   WeatherGPT UI   Leaflet Maps   ElevenLabs TTS
  (NWP Dashboard   (Multi-Model    (Multilingual
   & Comparison)    NWP Layers)     EN/HI/TE)
```

---

## 3. Core Architectural Principles & Separation of Concerns

1. **Separation of Observation vs NWP Forecast**:
   - **OpenWeatherMap (OWM)**: Strictly treated as **Observational / Reference Ground Truth** for current conditions and historical verification. OWM is NEVER misrepresented as an NWP model.
   - **NWP Models (GFS, WRF, ECMWF, BFS)**: Strictly treated as **Numerical Weather Prediction Model Forecasts** with distinct initializations, physics parameterizations, and forecast horizons.
   - **Blended Forecast**: Explicitly demarcated as the **AI-Synthesized Consensus Forecast**.

2. **Grounded AI Generation (Zero Hallucination)**:
   - Google Gemini is strictly a natural-language explanatory synthesis layer.
   - Gemini NEVER generates, hallucinates, or extrapolates raw meteorological numerical values.
   - All numbers, probabilities, model weights, and confidence ratings originate deterministically from the blending pipeline and are passed to Gemini via structured JSON context.

3. **Demarcation of Weather Alerts**:
   - **Model-Based Risk Alerts**: Algorithmically derived by evaluating blended forecasts against meteorological thresholds (e.g., >64.5 mm/day heavy rainfall).
   - **Official IMD / NDMA CAP Warnings**: Ingested directly from official CAP v1.2 feeds with 4-color coded district alerts (Green, Yellow, Orange, Red).
   - Model predictions are NEVER presented as official government warnings.

4. **Transparent & Explainable Weighting**:
   - Every blended forecast exposes the exact weights assigned to each model (e.g., GFS: 42%, WRF: 37%, ECMWF: 21%).
   - Confidence scores (0–100% / LOW, MEDIUM, HIGH) and model disagreement metrics (variance, spread, inter-model range) are computed deterministically with transparent mathematical formulations.

---

## 4. Subsystem Breakdown

### 4.1. NWP Ingestion & Provider Abstraction
- **Abstract Base Class**: `NWPProvider` with methods `get_forecast(location, lat, lon)`, `get_available_models()`, `get_metadata()`.
- **Implementations**:
  - `GFSProvider`: NOAA Global Forecast System (0.25° horizontal resolution).
  - `WRFProvider`: Weather Research and Forecasting mesoscale model (3–9 km resolution).
  - `ECMWFProvider`: European Centre for Medium-Range Weather Forecasts (IFS cycle).
  - `DemoNWPProvider`: High-fidelity synthetic NWP generator clearly labeled as `DEMO / SIMULATED NWP DATA`.

### 4.2. Standardization & Normalization Schema
Common internal schema for every forecast point:
```json
{
  "model_name": "GFS",
  "provider": "NOAA-NCEP",
  "latitude": 17.6868,
  "longitude": 83.2185,
  "issue_time": "2026-09-30T12:00:00Z",
  "valid_time": "2026-10-01T00:00:00Z",
  "lead_time_hours": 12,
  "temperature_2m_c": 28.4,
  "dew_point_2m_c": 23.1,
  "relative_humidity_pct": 74,
  "surface_pressure_hpa": 1010.5,
  "sea_level_pressure_hpa": 1012.0,
  "wind_speed_10m_kmh": 18.5,
  "wind_direction_10m_deg": 195,
  "wind_gust_10m_kmh": 26.0,
  "precipitation_amount_mm": 4.2,
  "precipitation_probability_pct": 65.0,
  "cloud_cover_pct": 80,
  "weather_regime": "monsoon_convective",
  "metadata": {"grid_res": "0.25deg", "cycle": "12Z"}
}
```

### 4.3. Historical Model Skill & Verification Service
Calculates verification metrics comparing past model predictions against observations:
- **Continuous Metrics**:
  $$\text{MAE} = \frac{1}{N}\sum |f_i - o_i|, \quad \text{RMSE} = \sqrt{\frac{1}{N}\sum (f_i - o_i)^2}, \quad \text{Bias} = \frac{1}{N}\sum (f_i - o_i)$$
- **Categorical Metrics (Precipitation Thresholds)**:
  $$\text{POD} = \frac{\text{Hits}}{\text{Hits} + \text{Misses}}, \quad \text{FAR} = \frac{\text{False Alarms}}{\text{Hits} + \text{False Alarms}}, \quad \text{CSI} = \frac{\text{Hits}}{\text{Hits} + \text{Misses} + \text{False Alarms}}$$
- **ModelSkill Record**: Stored by model, region, season, variable, lead time, and weather regime.

### 4.4. AI / Adaptive Weighting Engine
Computes normalized dynamic weights $w_m$ satisfying:
$$w_m \ge 0, \quad \sum_{m=1}^M w_m = 1.0$$
- **Baseline Deterministic Weighting**:
  Inverse-error weighting adjusted by lead time and weather regime:
  $$s_m = \frac{1}{\text{MAE}_m(v, \tau, R) + \epsilon} \times \gamma_m(\tau), \quad w_m = \frac{s_m}{\sum_{k=1}^M s_k}$$
  where $\tau$ is lead time, $R$ is regime, and $\gamma$ is a lead-time decay factor.
- **ML Meta-Learner Extension**: Ridge/Gradient Boosting / Random Forest meta-regressor trained on historical forecast residuals.

### 4.5. Multi-Model Forecast Blender
Synthesizes the consensus forecast:
$$\hat{Y}_{v, \tau} = \sum_{m=1}^M w_m(v, \tau) \cdot Y_{m, v, \tau}$$
Supports:
- Temperature ($^\circ\text{C}$)
- Total Precipitation (mm) & Precipitation Probability (%)
- Wind Speed (km/h) & Vector Wind Direction
- Surface Pressure (hPa) & Relative Humidity (%)

### 4.6. Confidence & Model Disagreement Engine
- **Model Disagreement**:
  Weighted standard deviation:
  $$\sigma = \sqrt{\sum_{m=1}^M w_m (Y_m - \hat{Y})^2}$$
  Spread ratio: $\Delta = \max(Y_m) - \min(Y_m)$.
- **Confidence Formulation**:
  $$C = 100 \times \left( \alpha \cdot \text{AgreementScore} + \beta \cdot \text{SkillScore} + \gamma \cdot \text{AvailabilityFactor} - \delta \cdot \text{LeadTimePenalty} \right)$$
  Classified into **HIGH** ($\ge 75\%$), **MEDIUM** ($50–74\%$), **LOW** ($< 50\%$).

### 4.7. Extreme Weather Alert Engine
Evaluates blended forecasts against standard meteorological criteria:
- **Heavy Rainfall**: Yellow (>15.6 mm/3h), Orange (>64.5 mm/24h), Red (>115.5 mm/24h).
- **Heatwave**: Temp $\ge 40^\circ\text{C}$ and departure $\ge 4.5^\circ\text{C}$ above normal.
- **Gale / Cyclone Wind**: Sustained wind $> 50\text{ km/h}$ or gusts $> 70\text{ km/h}$.
- **Severe Thunderstorm**: High CAPE/moisture + rain + lightning risk.

### 4.8. Grounded Gemini AI & Voice Layer
- Formats blended payload into structured meteorological context.
- Gemini produces human-readable, domain-tailored explanations (public, farmers, aviation, marine).
- Multi-script support: English, Hindi (Devanagari), Telugu.
- ElevenLabs TTS delivers low-latency server-side voice output.

### 4.9. UI / NWP Dashboard Layer
- Integrated into the existing WeatherGPT UI without breaking layout.
- Provides:
  1. Current Weather (Observation)
  2. Model Comparison (Side-by-side GFS vs WRF vs ECMWF)
  3. Dynamic Weights Breakdown (Visual progress bars / percentages)
  4. Blended Forecast Timeline
  5. Confidence Gauge & Disagreement Metric
  6. Model Disagreement Bar Chart
  7. Risk Alert Badges
  8. Interactive Multi-Model Forecast Map
