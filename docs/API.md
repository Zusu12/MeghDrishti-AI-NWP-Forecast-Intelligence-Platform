# REST API Specification
## MeghDrishti — AI–NWP Forecast Intelligence Platform (SIH26081)

---

## Base URL
`/` (Default: `http://localhost:8000`)

---

## Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/weather/current` | Current observational ground-truth from OpenWeatherMap |
| `GET` | `/api/forecast` | Standard observational multi-day forecast |
| `GET` | `/api/nwp/models` | List all registered NWP models and capabilities |
| `GET` | `/api/nwp/forecast` | Retrieve normalized forecast from a single model (`model=GFS`) |
| `GET` | `/api/nwp/compare` | Side-by-side comparison of GFS, WRF, ECMWF, and Consensus Blend |
| `GET` | `/api/nwp/blended` | Full 120-hour consensus blended forecast with weights & confidence |
| `GET` | `/api/nwp/weights` | Dynamic model weights breakdown for variable & lead time |
| `GET` | `/api/nwp/weight-map` | Regional model weight distributions across India |
| `GET` | `/api/nwp/confidence` | Detailed confidence metrics and explainability factors |
| `GET` | `/api/nwp/disagreement` | Inter-model spread ($\sigma$), range ($\Delta$), and variance |
| `GET` | `/api/nwp/skill` | Historical skill metrics (MAE, RMSE, Bias, CSI) |
| `GET` | `/api/nwp/verification` | Empirical verification comparing single models vs Blended |
| `GET` | `/api/extreme-weather` | Model-based extreme weather risk indicators |
| `GET` | `/api/workflow/status` | Operational pipeline telemetry and provider health |
| `POST` | `/api/workflow/run` | Trigger an immediate operational blending run |
| `GET` | `/alerts/official` | Authoritative IMD / NDMA CAP v1.2 district warnings |
