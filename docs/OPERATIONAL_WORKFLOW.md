# Operational Blending Workflow & Automation
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. 13-Stage Operational Pipeline

The official SIH26081 problem statement explicitly requires an automated operational workflow so forecasters and decision-makers do not perform manual ad-hoc computations.

```
Stage 1: NWP Ingestion (Parallel fetch of GFS, WRF, ECMWF)
   ↓
Stage 2: Validation (Physical limit clamps & quality control)
   ↓
Stage 3: Normalization (Spatiotemporal grid mapping & unit conversion)
   ↓
Stage 4: Storage (Persist raw model timesteps in cache & DB)
   ↓
Stage 5: Historical Skill Lookup (Retrieve regional MAE & CSI matrices)
   ↓
Stage 6: Weather Regime Detection (Rule-based atmospheric state identification)
   ↓
Stage 7: Adaptive Model Weighting (Dynamic inverse-skill calculation)
   ↓
Stage 8: Consensus Forecast Blending (Vector wind + scalar weighted blend)
   ↓
Stage 9: Confidence Quantification (Agreement score, coverage, lead decay)
   ↓
Stage 10: Model Disagreement Calculation (Weighted variance σ and range Δ)
   ↓
Stage 11: Extreme Weather Guidance (Threshold evaluation)
   ↓
Stage 12: Final Consensus Storage (Persist blended timeline to DB)
   ↓
Stage 13: Dashboard Update (Live telemetry and UI visualization)
```

---

## 2. Scheduling & Execution

- **Automated Mode:** Asynchronous background scheduler running every 3 hours ($10800\text{ seconds}$).
- **Manual Trigger:** On-demand via REST endpoint `POST /api/workflow/run?location=Visakhapatnam`.
- **Latency:** Typical execution latency is $<150\text{ ms}$ due to parallel asynchronous I/O and vectorized math.
