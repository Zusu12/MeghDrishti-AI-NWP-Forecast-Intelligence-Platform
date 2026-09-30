# Adaptive Model Weighting Engine
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Overview & Problem Definition

A core tenet of meteorological forecasting is that no single model is universally superior:
- **NOAA GFS** provides robust large-scale synoptic circulation over medium-range horizons (72–120h).
- **WRF-ARW** excels in localized boundary-layer dynamics, sea-breeze convergence, and orographic precipitation enhancement in complex terrain.
- **ECMWF IFS** demonstrates superior geopotential height tracking and tropical cyclone central pressure accuracy.

The Adaptive Model Weighting Engine computes dynamic weights $w_m$ that vary dynamically across:
1. **Forecast Lead Time ($\tau$):** $0\text{ to }120\text{ hours}$
2. **Geographic Region ($R$):** Coastal plains, Western Ghats, Gangetic basin, Deccan plateau
3. **Climatological Season ($S$):** Monsoon, Pre-Monsoon, Post-Monsoon, Winter
4. **Atmospheric Weather Regime ($K$):** Normal, Convective, Monsoon, Heavy Rain, Heatwave, Cyclone

---

## 2. Mathematical Formulation

### 2.1. Dynamic Weight Constraints
For $M$ operational models, the weights $w_m$ must strictly satisfy:
$$w_m \ge 0, \quad \sum_{m=1}^M w_m = 1.0$$

### 2.2. Baseline Inverse-Skill Weighting
The unnormalized raw score $s_m$ is computed using historical Mean Absolute Error (MAE):
$$s_m(v, \tau, R, K) = \frac{1}{\text{MAE}_m(v, \tau, R, K) + \epsilon} \cdot \alpha_m(\tau) \cdot \gamma_m(K)$$

where:
- $\epsilon = 0.01$ ensures numerical stability when error approaches zero.
- $\alpha_m(\tau)$ is the lead-time decay factor. At lead times $>72\text{ hours}$, models with faster error growth receive a mild penalty.
- $\gamma_m(K)$ is the regime sensitivity factor. Under convective regimes, high-resolution mesoscale WRF receives an empirical boost ($\times 1.35$), whereas under quiescent synoptic regimes ECMWF is weighted highest ($\times 1.15$).

### 2.3. Normalization
$$w_m(v, \tau) = \frac{s_m(v, \tau, R, K)}{\sum_{j=1}^M s_j(v, \tau, R, K)}$$

---

## 3. Spatial Weight Distribution (Weight Maps)

The system computes geographic weight distributions across India's meteorological subdivisions:
- **Coastal Andhra Pradesh (Visakhapatnam):** WRF: 44%, GFS: 32%, ECMWF: 24%
- **Western Ghats / Mumbai:** WRF: 48%, ECMWF: 28%, GFS: 24%
- **North-West Plains / New Delhi:** ECMWF: 40%, GFS: 35%, WRF: 25%
- **Gangetic West Bengal / Kolkata:** WRF: 42%, ECMWF: 33%, GFS: 25%
- **South Interior / Bengaluru:** ECMWF: 38%, WRF: 36%, GFS: 26%
