# NWP Data Sources Specification
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Overview of Forecast & Observation Sources

The Hybrid AI–NWP Multi-Model Forecast Blending System ingests and synthesizes heterogeneous gridded numerical model outputs with ground-truth observations. In strict compliance with meteorological standards, observations are cleanly separated from numerical model forecasts.

---

## 2. Ingested NWP Models

### 2.1. NOAA Global Forecast System (GFS 0.25°)
- **Institution:** National Centers for Environmental Prediction (NCEP), NOAA, USA.
- **Model Core:** Non-hydrostatic Global Spectral Model / FV3 dynamic core.
- **Horizontal Resolution:** $0.25^\circ \times 0.25^\circ$ (~28 km).
- **Temporal Resolution:** 3-hourly forecast steps out to 120 hours (5 days).
- **Cycle Runs:** 00Z, 06Z, 12Z, 18Z UTC.
- **Characteristics:** Highly stable global synoptic flow representation; slightly elevated precipitation spread in equatorial maritime zones.
- **License / Access:** Public Domain (NOAA Open Data Dissemination / AWS S3 / NOMADS).

### 2.2. Weather Research and Forecasting Model (WRF-ARW v4.4)
- **Institution:** National Center for Atmospheric Research (NCAR), USA / Regional Operational Centers.
- **Model Core:** Advanced Research WRF (ARW) non-hydrostatic, compressible solver.
- **Horizontal Resolution:** 3 km – 9 km Convective-Permitting Mesoscale Grid.
- **Temporal Resolution:** 3-hourly forecast steps out to 120 hours.
- **Physics Schemes:** WSM6 microphysics, YSU planetary boundary layer, Kain-Fritsch / explicit convection.
- **Characteristics:** Superior representation of localized orographic precipitation along the Western Ghats and Coastal Andhra Pradesh; sensitive to initial lateral boundary conditions.
- **License / Access:** Open-source community model (NCAR/UCAR).

### 2.3. ECMWF Integrated Forecasting System (IFS HRES)
- **Institution:** European Centre for Medium-Range Weather Forecasts, Reading, UK.
- **Model Core:** Semi-Lagrangian, semi-implicit hydrostatic/non-hydrostatic spectral core.
- **Horizontal Resolution:** 9 km Global High-Resolution (HRES).
- **Temporal Resolution:** 3-hourly forecast steps out to 120 hours.
- **Cycle Runs:** 00Z, 12Z UTC.
- **Characteristics:** Benchmark global skill scores for tropical synoptic tracking, pressure depth, and 500 hPa geopotential height fields.
- **License / Access:** ECMWF Open Data Policy (CC-BY 4.0 / WMO WIS2.0).

---

## 3. Observational / Ground Truth Reference Sources

### 3.1. OpenWeatherMap Observational Feed
- **Role:** Strictly **Current Observation & Ground-Truth Reference**.
- **Data:** Surface AWS stations, METAR airfield reports, and radar integration.
- **Usage Rule:** NEVER misclassified or cited as an NWP physical model.

### 3.2. Automatic Weather Station (AWS) Grid via MQTT
- **Role:** Real-time localized observational surface telemetry.
- **Protocol:** MQTT pub/sub over JSON payloads.

### 3.3. WMO WIS2.0 Global Broker
- **Role:** WMO Information System 2.0 real-time notification messages (`in-imd`).
- **Standard:** WNM (WIS2 Notification Message) GeoJSON payload metadata.
