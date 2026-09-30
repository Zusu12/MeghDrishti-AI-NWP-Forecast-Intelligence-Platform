"""
nwp/providers/demo_provider.py — High-Fidelity Synthetic NWP Provider
Strictly for offline development, integration testing, and demo reliability.
ALL outputs are unambiguously labeled as "DEMO / SIMULATED DATA".
"""
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from nwp.provider_base import ForecastProvider
from nwp.normalization import normalize_forecast_record
from schemas.forecast import ForecastSeries, StandardForecastPoint


class DemoNWPProvider(ForecastProvider):
    """
    Deterministic synthetic NWP generator.
    Produces 40 timesteps (120 hours / 5 days) at 3-hourly intervals.
    """
    provider_id = "demo"
    model_name = "SIMULATED-NWP"
    grid_resolution = "0.25° (~28 km Synthetic Grid)"
    time_step = "3-Hourly"
    forecast_horizon = "120 Hours (5 Days)"
    is_operational = False

    def __init__(self, model_name: str = "SIMULATED-NWP", bias_temp: float = 0.0, bias_rain: float = 0.0):
        self.model_name = model_name
        self.bias_temp = bias_temp
        self.bias_rain = bias_rain

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "grid_resolution": self.grid_resolution,
            "time_step": self.time_step,
            "forecast_horizon": self.forecast_horizon,
            "is_operational": False,
            "disclaimer": "DEMO / SIMULATED DATA — For demonstration and offline testing only.",
        }

    async def get_forecast(
        self,
        location: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> ForecastSeries:
        base_lat = lat if lat is not None else 17.6868
        base_lon = lon if lon is not None else 83.2185
        loc_name = location or f"Lat {round(base_lat, 2)}, Lon {round(base_lon, 2)}"

        seed_str = f"{self.model_name}:{loc_name}:{round(base_lat, 2)}:{round(base_lon, 2)}"
        rnd = random.Random(hash(seed_str) % 100000)

        now = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
        issue_time_iso = now.isoformat()

        points = []
        base_temp = 28.0 + self.bias_temp
        base_pres = 1012.0

        for i in range(40):
            step_hours = i * 3
            step_dt = now + timedelta(hours=step_hours)
            valid_time_iso = step_dt.isoformat()

            # Diurnal atmospheric oscillation
            diurnal_rad = (step_dt.hour / 24.0) * 2.0 * math.pi
            diurnal_factor = math.sin(diurnal_rad - 2.0)  # Peak around 14:00 UTC / Afternoon

            temp = round(base_temp + 4.0 * diurnal_factor + rnd.gauss(0, 0.4), 2)
            rh = round(max(30.0, min(95.0, 72.0 - 18.0 * diurnal_factor + rnd.gauss(0, 2.5))), 1)
            pres = round(base_pres - 3.0 * diurnal_factor + rnd.gauss(0, 0.6), 1)

            wind_ms = max(0.5, 4.2 + 2.0 * abs(diurnal_factor) + rnd.gauss(0, 0.8))
            wind_deg = round((195.0 + rnd.gauss(0, 20.0)) % 360.0, 1)

            # Rain cycle with model-specific bias
            rain_chance = max(0.0, min(1.0, 0.28 + 0.25 * math.sin(i / 6.0) + rnd.gauss(0, 0.12) + (self.bias_rain * 0.05)))
            precip = round(max(0.0, rnd.gauss(3.5 + self.bias_rain, 2.0)), 2) if rain_chance > 0.62 else 0.0
            pop = round(rain_chance * 100.0, 1)

            clouds = round(max(10.0, min(100.0, 40.0 + 35.0 * rain_chance + rnd.gauss(0, 4.0))), 1)

            raw_dict = {
                "temperature": temp,
                "humidity": rh,
                "pressure": pres,
                "wind_speed": wind_ms,
                "wind_unit": "ms",
                "wind_direction": wind_deg,
                "precipitation": precip,
                "precipitation_probability": pop,
                "cloud_cover": clouds,
                "weather_regime": "monsoon" if precip > 10.0 else "normal",
                "metadata": {"step_index": i, "simulated_bias_t": self.bias_temp},
            }

            norm_point = normalize_forecast_record(
                raw=raw_dict,
                model_name=self.model_name,
                provider=f"DEMO-{self.model_name}",
                lat=base_lat,
                lon=base_lon,
                issue_time=issue_time_iso,
                valid_time=valid_time_iso,
                lead_time_hours=step_hours,
                data_source="demo_simulated",
            )
            points.append(norm_point)

        return ForecastSeries(
            model_name=self.model_name,
            provider=f"DEMO-{self.model_name}",
            location_name=f"{loc_name} (DEMO)",
            latitude=base_lat,
            longitude=base_lon,
            issue_time=issue_time_iso,
            points=points,
            data_source="demo_simulated",
            is_demo=True,
            disclaimer="DEMO / SIMULATED NWP DATA — For evaluation and testing only.",
        )
