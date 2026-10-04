"""ECMWF IFS provider backed by a model-specific public feed."""
import asyncio
from typing import Any, Dict, Optional
import config
from nwp.provider_base import ForecastProvider
from nwp.providers.open_meteo import fetch_model
from nwp.providers.demo_provider import DemoNWPProvider
from schemas.forecast import ForecastSeries

class ECMWFProvider(ForecastProvider):
    provider_id="ecmwf"; model_name="ECMWF"; grid_resolution="9 km IFS HRES"; time_step="3-Hourly"; forecast_horizon="120 Hours (5 Days)"; is_operational=True
    def get_metadata(self)->Dict[str,Any]:
        return {"provider_id":self.provider_id,"model_name":"ECMWF Integrated Forecasting System (IFS HRES)","grid_resolution":self.grid_resolution,"time_step":self.time_step,"forecast_horizon":self.forecast_horizon,"institution":"ECMWF","is_operational":True,"data_source":"ECMWF IFS via model-specific Open-Meteo endpoint"}
    async def get_forecast(self,location:Optional[str]=None,lat:Optional[float]=None,lon:Optional[float]=None)->ForecastSeries:
        if config.NWP_DEMO_MODE:
            return await DemoNWPProvider(model_name="ECMWF",bias_temp=0.1,bias_rain=-0.2).get_forecast(location=location,lat=lat,lon=lon)
        return await asyncio.to_thread(fetch_model,model_endpoint="ecmwf",model_name="ECMWF",provider="ECMWF-IFS",location=location,lat=lat,lon=lon,resolution="9 km HRES")
