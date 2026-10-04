"""NOAA GFS provider backed by a model-specific public feed."""
import asyncio
from typing import Any, Dict, Optional
import config
from nwp.provider_base import ForecastProvider
from nwp.providers.open_meteo import fetch_model
from nwp.providers.demo_provider import DemoNWPProvider
from schemas.forecast import ForecastSeries

class GFSProvider(ForecastProvider):
    provider_id="gfs"; model_name="GFS"; grid_resolution="0.25° (~28 km) Global Grid"; time_step="3-Hourly"; forecast_horizon="120 Hours (5 Days)"; is_operational=True
    def get_metadata(self)->Dict[str,Any]:
        return {"provider_id":self.provider_id,"model_name":"NOAA Global Forecast System (GFS 0.25°)","grid_resolution":self.grid_resolution,"time_step":self.time_step,"forecast_horizon":self.forecast_horizon,"institution":"NOAA / NCEP","is_operational":True,"data_source":"NOAA GFS via model-specific Open-Meteo endpoint"}
    async def get_forecast(self,location:Optional[str]=None,lat:Optional[float]=None,lon:Optional[float]=None)->ForecastSeries:
        if config.NWP_DEMO_MODE:
            return await DemoNWPProvider(model_name="GFS",bias_temp=-0.4,bias_rain=0.6).get_forecast(location=location,lat=lat,lon=lon)
        return await asyncio.to_thread(fetch_model,model_endpoint="gfs",model_name="GFS",provider="NOAA-GFS",location=location,lat=lat,lon=lon,resolution="0.25°")
