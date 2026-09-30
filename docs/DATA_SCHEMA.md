# Standardized Meteorological Data Schema
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Schema Design Principles

To combine disparate NWP model grids (GFS 0.25°, WRF 3–9km, ECMWF 9km) and observational sensors into an operational consensus pipeline, all incoming records are converted into a common standardized schema: `StandardForecastPoint`.

All units are strictly standardized to the International System of Units (SI) / WMO meteorological conventions:
- **Temperature:** Celsius ($^\circ\text{C}$)
- **Precipitation:** Millimeters ($\text{mm}$ accumulated over step)
- **Precipitation Probability (PoP):** Percentage ($0 - 100\%$)
- **Wind Speed:** Kilometers per hour ($\text{km/h}$) and meters per second ($\text{m/s}$)
- **Wind Direction:** Degrees ($0 - 360^\circ$ meteorological convention)
- **Atmospheric Pressure:** Hectopascals ($\text{hPa} / \text{mb}$)
- **Relative Humidity:** Percentage ($0 - 100\%$)

---

## 2. StandardForecastPoint Schema (JSON Specification)

```json
{
  "model_name": "GFS",
  "provider": "NOAA-GFS",
  "latitude": 17.6868,
  "longitude": 83.2185,
  "issue_time": "2026-10-01T00:00:00Z",
  "valid_time": "2026-10-01T03:00:00Z",
  "lead_time_hours": 3,
  "temperature": 29.4,
  "dew_point": 23.2,
  "humidity": 76.0,
  "pressure": 1010.5,
  "wind_speed": 16.5,
  "wind_direction": 195.0,
  "precipitation": 3.8,
  "precipitation_probability": 70.0,
  "cloud_cover": 65.0,
  "weather_regime": "monsoon",
  "data_source": "live_nwp",
  "metadata": {
    "grid_resolution": "0.25deg",
    "cycle": "00Z"
  }
}
```

---

## 3. Blended Consensus Output Schema

```json
{
  "valid_time": "2026-10-01 03:00:00",
  "lead_time_hours": 3,
  "dt": 1727751600,
  "temperature": 29.1,
  "precipitation": 3.4,
  "precipitation_probability": 68.0,
  "wind_speed": 15.8,
  "wind_direction": 192.5,
  "pressure": 1010.8,
  "humidity": 75.2,
  "individual_models": {
    "GFS": {"temperature": 28.8, "precipitation": 3.1, "wind_speed": 16.0},
    "WRF": {"temperature": 29.4, "precipitation": 4.2, "wind_speed": 16.8},
    "ECMWF": {"temperature": 29.0, "precipitation": 2.9, "wind_speed": 14.5}
  },
  "model_weights": {
    "GFS": 0.32,
    "WRF": 0.44,
    "ECMWF": 0.24
  },
  "confidence": {
    "score_pct": 84.5,
    "category": "HIGH",
    "agreement_score": 0.88,
    "disagreement_spread": 0.42,
    "inter_model_range": 1.10,
    "active_models_count": 3,
    "factors": [
      "3/3 NWP models actively contributing to consensus.",
      "Strong inter-model agreement (spread: 0.42, range: 1.10).",
      "Short forecast horizon (3h lead) enhances reliability."
    ]
  },
  "extreme_alerts": [],
  "weather_regime": "monsoon",
  "data_source": "hybrid_blended_nwp"
}
```
