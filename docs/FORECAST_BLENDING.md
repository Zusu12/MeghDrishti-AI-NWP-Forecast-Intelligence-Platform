# Multi-Model Forecast Blending Engine
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Overview & Blending Principle

Consensus forecasting synthesizes individual model runs into an optimal single deterministic prediction:
$$\hat{Y}_{v, \tau} = \sum_{m=1}^M w_m(v, \tau) \cdot Y_{m, v, \tau}$$

---

## 2. Scalar vs Vector Blending

### 2.1. Continuous Scalar Variables
For Temperature ($^\circ\text{C}$), Precipitation Amount ($\text{mm}$), Pressure ($\text{hPa}$), and Humidity ($\%$), blending is a weighted linear summation.

For Precipitation Probability ($\text{PoP}$):
$$\widehat{\text{PoP}}_{\tau} = \sum_{m=1}^M w_m(\text{precip}, \tau) \cdot \text{PoP}_{m, \tau}$$

### 2.2. Vector Wind Blending
Linear averaging of meteorological angles produces critical errors near North ($350^\circ$ and $10^\circ$ average linearly to $180^\circ$ South, which is completely incorrect).

The system decomposes horizontal winds into orthogonal Cartesian vector components:
$$u_m = -S_m \cdot \sin(\theta_m), \quad v_m = -S_m \cdot \cos(\theta_m)$$

where $S_m$ is wind speed ($\text{km/h}$) and $\theta_m$ is wind direction in radians.

Weighted consensus vector:
$$\hat{u} = \sum_{m=1}^M w_m \cdot u_m, \quad \hat{v} = \sum_{m=1}^M w_m \cdot v_m$$

Reconstruction:
$$\hat{S} = \sqrt{\hat{u}^2 + \hat{v}^2}, \quad \hat{\theta} = \left( \frac{180}{\pi} \cdot \text{atan2}(-\hat{u}, -\hat{v}) \right) \pmod{360}$$
