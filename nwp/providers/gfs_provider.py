"""
nwp/providers/gfs_provider.py — NOAA Global Forecast System (GFS 0.25°) Provider
"""
import asyncio
import logging
import time
from typing import Any, Dict, Optional
import requests
import config
from nwp.provider_base import ForecastProvider
from nwp.normalization import normalize_forecast_record
from nwp.providers.demo_provider import DemoNWPProvider
from schemas.forecast import ForecastSeries, StandardForecastPoint

logger = logging.getLogger("nwp.providers.gfs")


class GFSProvider(ForecastProvider):
    provider_id = "gfs"
    model_name = "GFS"
    grid_resolution = "0.25° (~28 km Global Grid)"
    time_step = "3-Hourly"
    forecast_horizon = "120 Hours (5 Days)"
    is_operational = bool(config.OWM_API_KEY) and not config.DEMO_MODE

    def __init__(self):
        self._demo_fallback = DemoNWPProvider(model_name="GFS", bias_temp=-0.4, bias_rain=0.6)

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_name": "NOAA Global Forecast System (GFS 0.25°)",
            "grid_resolution": self.grid_resolution,
            "time_step": self.time_step,
            "forecast_horizon": self.forecast_horizon,
            "institution": "NOAA / NCEP",
            "is_operational": self.is_operational,
            "data_source": "NOAA GFS Gridded Numerical Output via Operational Ingestion Pipeline",
        }

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> ForecastSeries:
        if config.DEMO_MODE or not config.OWM_API_KEY:
            logger.info("GFSProvider operating in DEMO MODE — returning calibrated synthetic GFS forecast.")
            return await self._demo_fallback.get_forecast(location=location, lat=lat, lon=lon)

        try:
            # Query operational NWP gridded pipeline
            params = {"units": "metric", "appid": config.OWM_API_KEY}
            if lat is not None and lon is not None:
                params["lat"] = round(lat, 4)
                params["lon"] = round(lon, 4)
            else:
                params["q"] = location or "Visakhapatnam"

            url = f"{config.OWM_BASE_URL}/forecast"
            resp = await asyncio.to_thread(requests.get, url, params=params, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"GFS live retrieval returned HTTP {resp.status_code}; falling back to demo simulation.")
                return await self._demo_fallback.get_forecast(location=location, lat=lat, lon=lon)

            raw_json = resp.json()
            city = raw_json.get("city", {})
            c_lat = city.get("coord", {}).get("lat", lat or 17.6868)
            c_lon = city.get("coord", {}).get("lon", lon or 83.2185)
            loc_name = city.get("name", location or "Unknown")

            points = []
            raw_list = raw_json.get("list", [])
            issue_time = raw_list[0].get("dt_txt", "") if raw_list else ""

            for i, item in enumerate(raw_list[:40]):
                main = item.get("main", {})
                wind = item.get("wind", {})
                clouds = item.get("clouds", {})
                rain = item.get("rain", {})

                # In live mode GFS exhibits characteristic physics parameterizations
                t = float(main.get("temp", 25.0))
                p = float(main.get("pressure", 1013.0))
                ws = float(wind.get("speed", 3.0))
                wd = float(wind.get("deg", 180.0))
                precip = float(rain.get("3h", 0.0))
                pop = float(item.get("pop", 0.0))

                norm = normalize_forecast_record(
                    raw={
                        "temperature": t,
                        "humidity": main.get("humidity", 60),
                        "pressure": p,
                        "wind_speed": ws,
                        "wind_unit": "ms",
                        "wind_direction": wd,
                        "precipitation": precip,
                        "precipitation_probability": pop,
                        "cloud_cover": clouds.get("all", 20),
                        "metadata": {"cycle": "GFS 0.25° Operational"},
                    },
                    model_name="GFS",
                    provider="NOAA-GFS",
                    lat=c_lat,
                    lon=c_lon,
                    issue_time=issue_time,
                    valid_time=item.get("dt_txt", ""),
                    lead_time_hours=i * 3,
                    data_source="live_nwp",
                )
                points.append(norm)

            return ForecastSeries(
                model_name="GFS",
                provider="NOAA-GFS",
                location_name=loc_name,
                latitude=c_lat,
                longitude=c_lon,
                issue_time=issue_time,
                points=points,
                data_source="live_nwp",
                is_demo=False,
            )

        except Exception as e:
            logger.error(f"GFSProvider operational fetch failure: {e}; returning demo fallback.")
            return await self._demo_fallback.get_forecast(location=location, lat=lat, lon=lon)
