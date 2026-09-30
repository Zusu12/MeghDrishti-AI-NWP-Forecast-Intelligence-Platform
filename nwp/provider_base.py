"""
nwp/provider_base.py — Abstract Base Class for Forecast Providers
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from schemas.forecast import ForecastSeries


class ForecastProvider(ABC):
    """
    Abstract interface for meteorological forecast providers (GFS, WRF, ECMWF, Demo).
    Every provider must implement forecast retrieval and metadata capabilities.
    """
    provider_id: str
    model_name: str
    grid_resolution: str
    time_step: str
    forecast_horizon: str
    is_operational: bool

    @abstractmethod
    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> ForecastSeries:
        """Fetch and return standardized forecast series."""
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return provider technical specifications, horizontal grid resolution, and cycle times."""
        pass

    def get_status(self) -> str:
        """Return provider availability: AVAILABLE | DEGRADED | UNAVAILABLE | DEMO."""
        return "AVAILABLE" if self.is_operational else "DEMO"
