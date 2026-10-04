"""
nwp/manager.py — NWP Model Ingestion Coordinator & Manager
Fetches forecasts across multiple NWP providers concurrently with timeout protection,
caching, error isolation, and graceful fault recovery.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
import database
import config
from nwp.provider_base import ForecastProvider
from nwp.providers.gfs_provider import GFSProvider
from nwp.providers.wrf_provider import WRFProvider
from nwp.providers.ecmwf_provider import ECMWFProvider
from schemas.forecast import ForecastSeries

logger = logging.getLogger("nwp.manager")


class NWPManager:
    """Orchestrator for multi-model NWP forecast retrieval."""

    def __init__(self):
        self._providers: Dict[str, ForecastProvider] = {
            "GFS": GFSProvider(),
            "WRF": WRFProvider(),
            "ECMWF": ECMWFProvider(),
        }

    def register_provider(self, name: str, provider: ForecastProvider):
        """Dynamic extension point for additional NWP models (e.g. Bharat Forecast System)."""
        self._providers[name] = provider
        logger.info(f"Registered NWP provider: {name}")

    def get_available_models(self) -> List[Dict[str, str]]:
        """Return list and capabilities of registered models."""
        return [
            {
                "id": k,
                "name": v.model_name,
                "resolution": v.grid_resolution,
                "time_step": v.time_step,
                "horizon": v.forecast_horizon,
                "status": v.get_status(),
            }
            for k, v in self._providers.items()
        ]

    async def fetch_model_forecast(
        self,
        model_name: str,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Optional[ForecastSeries]:
        """Fetch forecast for a single model with caching."""
        provider = self._providers.get(model_name.upper())
        if not provider:
            logger.error(f"Unknown model provider requested: {model_name}")
            return None

        cache_key = f"nwp_v3:{model_name.lower()}:{location or f'{lat},{lon}'}"
        cached = await database.cache_get(cache_key)
        if cached:
            try:
                return ForecastSeries.model_validate(cached)
            except Exception:
                pass

        try:
            series = await asyncio.wait_for(
                provider.get_forecast(location=location, lat=lat, lon=lon),
                timeout=12.0
            )
            # Cache valid series
            await database.cache_set(cache_key, series.model_dump(), ttl=config.WEATHER_CACHE_TTL)
            return series
        except asyncio.TimeoutError:
            logger.warning(f"Timeout retrieving forecast from {model_name}.")
            return None
        except Exception as e:
            logger.error(f"Error fetching forecast from {model_name}: {e}")
            return None

    async def fetch_all_models(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Tuple[Dict[str, ForecastSeries], Dict[str, str]]:
        """
        Fetch forecasts across all registered models in parallel.
        Isolates failures: if one model fails, remaining models proceed.
        Returns:
            (successful_series_by_model, provider_health_status)
        """
        tasks = []
        model_names = list(self._providers.keys())

        for name in model_names:
            tasks.append(self.fetch_model_forecast(name, location=location, lat=lat, lon=lon))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        series_map: Dict[str, ForecastSeries] = {}
        health_status: Dict[str, str] = {}

        for name, res in zip(model_names, results):
            if isinstance(res, ForecastSeries):
                series_map[name] = res
                health_status[name] = "AVAILABLE" if not res.is_demo else "DEMO_MODE"
            else:
                logger.warning(f"Model {name} failed or returned error: {res}")
                health_status[name] = "UNAVAILABLE"

        return series_map, health_status


# Global singleton instance
nwp_manager = NWPManager()
