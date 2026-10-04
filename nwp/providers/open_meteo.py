"""Shared adapter for model-specific Open-Meteo feeds."""
from datetime import datetime, timezone
from typing import Optional
import requests
from nwp.normalization import normalize_forecast_record
from schemas.forecast import ForecastSeries

HOURLY="temperature_2m,relative_humidity_2m,dew_point_2m,surface_pressure,wind_speed_10m,wind_direction_10m,precipitation,precipitation_probability,cloud_cover"

def fetch_model(model_endpoint:str, model_name:str, provider:str, location:Optional[str], lat:Optional[float], lon:Optional[float], resolution:str)->ForecastSeries:
    lat=float(lat if lat is not None else 17.6868); lon=float(lon if lon is not None else 83.2185)
    params={"latitude":lat,"longitude":lon,"hourly":HOURLY,"forecast_hours":120,"temperature_unit":"celsius","wind_speed_unit":"kmh","precipitation_unit":"mm","timeformat":"iso8601","timezone":"GMT"}
    r=requests.get(f"https://api.open-meteo.com/v1/{model_endpoint}",params=params,timeout=15); r.raise_for_status()
    h=r.json().get("hourly",{}); times=h.get("time",[])
    if not times: raise RuntimeError(f"{model_name} returned no forecast data")
    issue=datetime.now(timezone.utc).isoformat(); points=[]
    for i in range(0,min(len(times),120),3):
        raw={"temperature":h["temperature_2m"][i],"humidity":h["relative_humidity_2m"][i],"dew_point":h["dew_point_2m"][i],"pressure":h["surface_pressure"][i],"wind_speed":h["wind_speed_10m"][i],"wind_unit":"kmh","wind_direction":h["wind_direction_10m"][i],"precipitation":h["precipitation"][i] or 0.0,"precipitation_probability":h["precipitation_probability"][i] or 0.0,"cloud_cover":h["cloud_cover"][i] or 0.0,"metadata":{"model":model_name,"resolution":resolution,"source":"Open-Meteo model-specific endpoint"}}
        points.append(normalize_forecast_record(raw,model_name,provider,lat,lon,issue,times[i],i,"live_nwp"))
    return ForecastSeries(model_name=model_name,provider=provider,location_name=location or f"Lat {lat:.2f}, Lon {lon:.2f}",latitude=lat,longitude=lon,issue_time=issue,points=points,data_source="live_nwp",is_demo=False,disclaimer="Model-specific feed; Open-Meteo documents the underlying NOAA GFS and ECMWF IFS sources.")

