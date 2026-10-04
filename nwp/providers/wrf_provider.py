"""
nwp/providers/wrf_provider.py — Weather Research and Forecasting (WRF-ARW) Mesoscale Provider
"""
import asyncio
import logging
import os
from typing import Any, Dict, Optional
import requests
import config
from nwp.provider_base import ForecastProvider
from nwp.normalization import normalize_forecast_record
from nwp.providers.demo_provider import DemoNWPProvider
from schemas.forecast import ForecastSeries, StandardForecastPoint

logger = logging.getLogger("nwp.providers.wrf")


class WRFProvider(ForecastProvider):
    provider_id = "wrf"
    model_name = "WRF"
    grid_resolution = "3 km - 9 km High-Res Mesoscale Grid"
    time_step = "3-Hourly"
    forecast_horizon = "120 Hours (5 Days)"
    is_operational = False

    def __init__(self):
        # WRF mesoscale tends to resolve localized convection and topography better,
        # with characteristic localized precipitation peaks.
        self._demo_fallback = DemoNWPProvider(model_name="WRF", bias_temp=0.5, bias_rain=1.4)

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_name": "Weather Research and Forecasting Model (WRF-ARW v4.4)",
            "grid_resolution": self.grid_resolution,
            "time_step": self.time_step,
            "forecast_horizon": self.forecast_horizon,
            "institution": "NCAR / Regional Mesoscale Downscaling Core",
            "is_operational": self.is_operational,
            "data_source": "High-Resolution Boundary Convective Surface Grids",
        }

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> ForecastSeries:
        if not os.getenv("WRF_FEED_URL"):
            raise RuntimeError("WRF_FEED_URL is not configured; WRF is unavailable rather than simulated.")

        raise RuntimeError("WRF_FEED_URL is configured, but no standardized WRF adapter is implemented yet. Provide a JSON feed adapter before enabling WRF.")
