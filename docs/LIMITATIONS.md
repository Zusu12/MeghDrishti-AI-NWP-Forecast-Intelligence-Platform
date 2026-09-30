# System Limitations & Future Scope
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Technical & Scientific Limitations

1. **Horizontal Grid Interpolation:**
   - The current baseline maps model grid points to regional centroid coordinates. High-resolution spatial bilinear or bicubic interpolation across continuous 2D grids can be enhanced in future iterations.
2. **Machine Learning Training Data:**
   - Baseline adaptive weighting uses empirical inverse-skill tables. Full ML regression meta-learners (e.g., XGBoost, Random Forest) require multi-year continuous reanalysis datasets (such as ERA5 / IMD gridded observations) to avoid overfitting.
3. **Statutory Warnings:**
   - Algorithmic extreme weather guidance is intended solely for decision support and does not replace official bulletins from IMD or NDMA.

---

## 2. Future Scope & Enhancements

1. Direct integration with India's Bharat Forecast System (NCMRWF unified model).
2. Deep learning spatial post-processing (Convolutional MOS / U-Net downscaling).
3. Integration of high-frequency Doppler Weather Radar (DWR) nowcasting data.
