# Target Architecture: MeghDrishti — AI–NWP Forecast Intelligence Platform
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. System Mission & Core Philosophy

The **MeghDrishti — AI–NWP Forecast Intelligence Platform** addresses the fundamental meteorological reality highlighted in SIH26081:

> *Different Numerical Weather Prediction (NWP) models exhibit varying predictive skill across geographic regions, climatological seasons, forecast lead times, and specific atmospheric weather regimes.*

Rather than relying on a single deterministic model (e.g. only NOAA GFS or only regional WRF), this platform implements a dynamic, automated AI-assisted weighting framework that blends multi-model predictions into an optimal, high-accuracy consensus forecast, quantifies forecast uncertainty, detects extreme weather risks, and presents transparent verification analytics through an operational dashboard.

The system is **NOT** a chatbot; it is a **professional meteorological intelligence and forecast blending platform**.

---

## 2. End-to-End Operational Pipeline

```
                ┌──────────────────────────────────────────────┐
                │        RAW METEOROLOGICAL DATA SOURCES       │
                └──────────────────────┬───────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        ▼                              ▼                              ▼
  NOAA GFS 0.25°                    WRF-ARW                       ECMWF IFS /
 Global Numerical             Regional Mesoscale              Global Cycle /
  Model Forecast                Model Forecast               Bharat Forecast
        │                              │                              │
        └──────────────────────────────┼──────────────────────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │      NWP DATA INGESTION      │
                       │    Providers, Retry, Cache   │
                       └──────────────┬───────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │      DATA NORMALIZATION      │
                       │  Units, Grids, Common Schema │
                       └──────────────┬───────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                ▼                                             ▼
  ┌──────────────────────────────┐              ┌──────────────────────────────┐
  │    OBSERVATION ALIGNMENT     │              │    WEATHER REGIME DETECT     │
  │   Ground Truth Reference     │              │  Monsoon, Convective, etc.   │
  │   (OpenWeather / AWS / WIS2) │              └──────────────┬───────────────┘
  └─────────────┬────────────────┘                             │
                │                                              │
                ▼                                              ▼
  ┌──────────────────────────────┐              ┌──────────────────────────────┐
  │    HISTORICAL MODEL SKILL    │              │   ADAPTIVE MODEL WEIGHTING   │
  │  MAE, RMSE, Bias, POD, CSI   ├─────────────►│ Dynamic Weights: w_m >= 0,   │
  └──────────────────────────────┘              │ Σ w_m = 1.0 (Lead/Regime/Loc)│
                                                └──────────────┬───────────────┘
                                                               │
                                                               ▼
                                                ┌──────────────────────────────┐
                                                │ MULTI-MODEL CONSENSUS BLEND  │
                                                │ Y_hat = Σ (w_m * Y_m)        │
                                                │ Vector-averaged wind (U, V)  │
                                                └──────────────┬───────────────┘
                                                               │
                       ┌───────────────────────────────────────┴───────────────────────────────────────┐
                       ▼                                       ▼                                       ▼
        ┌──────────────────────────────┐        ┌──────────────────────────────┐        ┌──────────────────────────────┐
        │       BLENDED FORECAST       │        │   CONFIDENCE & DISAGREEMENT  │        │   EXTREME WEATHER GUIDANCE   │
        │ T(2m), Rain, Wind, P, RH, PoP│        │ Spread σ, Range Δ, Confidence│        │ Heavy Rain, Heatwave, Wind   │
        └──────────────┬───────────────┘        └──────────────┬───────────────┘        └──────────────┬───────────────┘
                       │                                       │                                       │
                       └───────────────────────────────────────┼───────────────────────────────────────┘
                                                               ▼
                                                ┌──────────────────────────────┐
                                                │     FORECAST VERIFICATION    │
                                                │   Individual Models vs Blend │
                                                │   MAE, RMSE, CSI Improvement │
                                                └──────────────┬───────────────┘
                                                               ▼
                                                ┌──────────────────────────────┐
                                                │     OPERATIONAL DASHBOARD    │
                                                │  Forecast, Weights, Maps,    │
                                                │  Verification & Comparison   │
                                                └──────────────┬───────────────┘
                                                               ▲
                                                ┌──────────────┴───────────────┐
                                                │     AUTOMATED SCHEDULER      │
                                                │ Periodic 3h/6h NWP Ingestion │
                                                └──────────────────────────────┘
```

---

## 3. Detailed Component Specifications

### 3.1. Standardized Forecast Schema
Every forecast output from any model is mapped into a normalized record:
```json
{
  "model_name": "GFS",
  "provider": "NOAA-NCEP",
  "latitude": 17.6868,
  "longitude": 83.2185,
  "issue_time": "2026-09-30T12:00:00Z",
  "valid_time": "2026-10-01T00:00:00Z",
  "lead_time_hours": 12,
  "temperature": 28.4,
  "precipitation": 4.2,
  "precipitation_probability": 65.0,
  "wind_speed": 18.5,
  "wind_direction": 195.0,
  "pressure": 1010.5,
  "humidity": 74.0,
  "weather_regime": "monsoon",
  "metadata": {"grid_res": "0.25deg", "cycle": "12Z"},
  "data_source": "live_nwp"
}
```

### 3.2. Historical Model Skill & Verification Formulas
Verification computes performance metrics comparing forecasts ($f_i$) against observational ground truth ($o_i$) over sample size $N$:

1. **Mean Absolute Error (MAE):**
   $$\text{MAE} = \frac{1}{N}\sum_{i=1}^N |f_i - o_i|$$

2. **Root Mean Square Error (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{N}\sum_{i=1}^N (f_i - o_i)^2}$$

3. **Mean Bias Error (Bias):**
   $$\text{Bias} = \frac{1}{N}\sum_{i=1}^N (f_i - o_i)$$

4. **Categorical Metrics for Precipitation Events (Threshold: $\ge 15.6\text{ mm/3h}$ or $\ge 64.5\text{ mm/24h}$):**
   - **Probability of Detection (POD):**
     $$\text{POD} = \frac{\text{Hits}}{\text{Hits} + \text{Misses}}$$
   - **False Alarm Ratio (FAR):**
     $$\text{FAR} = \frac{\text{False Alarms}}{\text{Hits} + \text{False Alarms}}$$
   - **Critical Success Index (CSI / Threat Score):**
     $$\text{CSI} = \frac{\text{Hits}}{\text{Hits} + \text{Misses} + \text{False Alarms}}$$

### 3.3. Weather Regime Classification
Atmospheric conditions are categorized into distinct meteorological regimes:
- `normal`: Quiescent weather, standard diurnal cycles.
- `monsoon`: Sustained high moisture (>75% RH), broad synoptic southwesterly/northeasterly low-level jets.
- `heavy_rainfall`: Precipitable moisture and deep convection producing $>64.5\text{ mm/day}$.
- `convective`: High instability (high CAPE / low lifted index), localized thunderstorms.
- `heatwave`: Maximum temperature $\ge 40^\circ\text{C}$ with departure $\ge 4.5^\circ\text{C}$ above normal.
- `dry_spell`: Prolonged low humidity (<40%) and near-zero precipitation during typical wet seasons.
- `high_wind`: Sustained winds $\ge 50\text{ km/h}$.
- `storm_cyclone`: Deep low-pressure systems with gale force winds and torrential rain.

### 3.4. Adaptive Model Weighting Engine
Dynamic weights $w_m$ are determined dynamically per variable $v$, lead time $\tau$, region $R$, and weather regime $K$:

1. **Baseline Inverse-Skill Formulation:**
   $$s_m(v, \tau, R, K) = \frac{1}{\text{MAE}_m(v, \tau, R, K) + \epsilon} \times \alpha_m(\tau)$$
   where $\epsilon = 0.001$ prevents division by zero, and $\alpha_m(\tau) = \exp\left(-\lambda_m \frac{\tau}{120}\right)$ accounts for lead-time decay.

2. **Normalized Weights:**
   $$w_m(v, \tau) = \frac{s_m(v, \tau, R, K)}{\sum_{j=1}^M s_j(v, \tau, R, K)}$$
   Strict constraints enforced:
   $$w_m \ge 0, \quad \sum_{m=1}^M w_m = 1.0$$

3. **ML Meta-Learner Extension:**
   Trained regression ensemble (Ridge / Random Forest / Gradient Boosting) learning residual errors based on historical feature vectors:
   $$x = [\text{MAE}_m, \text{RMSE}_m, \text{Bias}_m, \tau, \text{RegimeId}, \text{SeasonId}, \text{RecentError}_m]$$

### 3.5. Multi-Model Consensus Blending Formulation
1. **Scalar Variables (Temperature, Rain Amount, Pressure, Humidity, PoP):**
   $$\hat{Y}_{v, \tau} = \sum_{m=1}^M w_m(v, \tau) \cdot Y_{m, v, \tau}$$

2. **Wind Speed & Direction (Vector Averaging):**
   Degrees must never be linearly averaged. Wind is decomposed into orthogonal components:
   $$u_m = -S_m \cdot \sin\left(\frac{\pi}{180} \cdot D_m\right), \quad v_m = -S_m \cdot \cos\left(\frac{\pi}{180} \cdot D_m\right)$$
   Blended vector components:
   $$\hat{u} = \sum_{m=1}^M w_m \cdot u_m, \quad \hat{v} = \sum_{m=1}^M w_m \cdot v_m$$
   Consensus wind speed and direction:
   $$\hat{S} = \sqrt{\hat{u}^2 + \hat{v}^2}, \quad \hat{D} = \left( \frac{180}{\pi} \cdot \text{atan2}(-\hat{u}, -\hat{v}) \right) \pmod{360}$$

### 3.6. Confidence & Model Disagreement Engine
1. **Weighted Inter-Model Variance & Spread:**
   $$\sigma_{v, \tau} = \sqrt{\sum_{m=1}^M w_m(v, \tau) \cdot \left(Y_{m, v, \tau} - \hat{Y}_{v, \tau}\right)^2}$$
2. **Inter-Model Range:**
   $$\Delta_{v, \tau} = \max_{m}(Y_{m, v, \tau}) - \min_{m}(Y_{m, v, \tau})$$
3. **Composite Confidence Score ($C \in [0, 100]\%$):**
   $$C = 100 \times \left( 0.40 \cdot S_{\text{agreement}} + 0.35 \cdot S_{\text{skill}} + 0.15 \cdot S_{\text{coverage}} - 0.10 \cdot P_{\text{leadtime}} \right)$$
   Categorical Ratings:
   - **HIGH:** $C \ge 75\%$ (Tight model clustering, high historical skill, short lead time)
   - **MEDIUM:** $50\% \le C < 75\%$
   - **LOW:** $C < 50\%$ (High model divergence or long forecast horizon)

### 3.7. Extreme Weather Guidance
Evaluates the consensus blended forecast against standardized meteorological criteria:
- **Heavy Rainfall:** Yellow Alert ($>15.6\text{ mm/3h}$), Orange Alert ($>64.5\text{ mm/24h}$), Red Alert ($>115.5\text{ mm/24h}$).
- **Heatwave:** Max Temperature $\ge 40^\circ\text{C}$ with departure $\ge 4.5^\circ\text{C}$ above climatological normal.
- **High Wind / Gale:** Sustained wind $> 50\text{ km/h}$ or gusts $> 70\text{ km/h}$.
- **Demarcation:** Formally displayed as **"Model-Based Risk Guidance"** and clearly distinguished from authoritative government warnings (e.g. IMD / NDMA).

---

## 4. UI / Dashboard Architecture

The user interface transforms into a scientific forecasting console:

1. **Dashboard:** Key metrics at a glance (Current Observation, Latest Blended Forecast, Model Weights breakdown, Confidence gauge, Extreme Weather signals, Timeline).
2. **Forecast:** Multi-step consensus forecast with temperature, rain, wind, and pressure charts.
3. **Model Comparison:** Side-by-side comparison matrix showing GFS vs WRF vs ECMWF vs Blended Consensus.
4. **Weight Maps:** Geographic map displaying the winning model and dynamic weight distribution across Indian meteorological subdivisions.
5. **Verification:** Real-time and historical evaluation graphs showing MAE, RMSE, and CSI improvements of the blended consensus over single models.
6. **Extreme Weather:** Risk indicators, threshold breaches, and model agreement on severe weather events.
7. **Operational Workflow:** Status monitor displaying data ingestion runs, model availability, last execution timestamp, and manual trigger (`Run Blending Cycle`).
8. **Map:** Multi-layer GIS viewer with layer toggles for Observation, GFS, WRF, Blended, Weight Maps, and Risk Polygons.
