# Demo Mode & Offline Reliability Specification
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Purpose of Demo Mode

During hackathon presentations, judging rounds, or offline testing, external meteorological APIs or internet connections may be unavailable.

Demo Mode ensures the entire 13-stage forecasting and blending pipeline runs end-to-end without network dependencies.

---

## 2. Scientific Labeling Rules

In strict compliance with meteorological ethics:
1. Every simulated output carries the flag `is_demo: true` and `data_source: "demo_simulated"`.
2. The UI explicitly displays: `"DEMO / SIMULATED DATA"`.
3. The application NEVER misrepresents synthetic model runs as real observations.

---

## 3. Real Data vs Demo Data Transition

- When `OPENWEATHERMAP_API_KEY` is present and `DEMO_MODE=False`, the application automatically uses real operational feeds.
- If upstream feeds return HTTP errors or time out, the system isolates the failure and falls back gracefully with clear logging.
