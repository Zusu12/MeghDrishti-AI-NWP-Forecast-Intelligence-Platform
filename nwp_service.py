"""
nwp_service.py — NWP model abstraction (GFS/WRF integration-ready stubs)
"""
import math
import random
from datetime import datetime, timedelta, timezone

NWP_DISCLAIMER = (
    "NWP MODEL LAYER — Architecture ready. "
    "GFS/WRF: prototype placeholder. Current source: OpenWeatherMap."
)


class NWPProvider:
    name = "base"
    def get_forecast(self, location: str) -> dict:
        raise NotImplementedError


class GFSProvider(NWPProvider):
    name = "GFS"
    def get_forecast(self, location: str) -> dict:
        return {"provider": "GFS", "status": "prototype_placeholder",
                "note": "Production: NOAA NOMADS API", "data": _demo_nwp(location, "GFS")}


class WRFProvider(NWPProvider):
    name = "WRF"
    def get_forecast(self, location: str) -> dict:
        return {"provider": "WRF", "status": "prototype_placeholder",
                "note": "Production: WRF-ARW server", "data": _demo_nwp(location, "WRF")}


def _demo_nwp(location: str, model: str) -> list:
    random.seed(hash(f"{location}{model}") % 2000)
    now = datetime.now(tz=timezone.utc)
    return [
        {
            "dt": (now + timedelta(hours=i * 3)).isoformat(),
            "temperature_2m": round(27 + 4 * math.sin(i / 8 * math.pi) + random.gauss(0, 1), 1),
            "wind_speed_10m": round(abs(random.gauss(15, 8)), 1),
            "total_precipitation": round(max(0, random.gauss(1, 3)), 1),
            "relative_humidity_2m": round(max(40, min(95, random.gauss(70, 10))), 0),
            "demo": True,
        }
        for i in range(16)
    ]


_providers = {"gfs": GFSProvider(), "wrf": WRFProvider()}


def get_nwp_forecast(location: str, provider: str = "gfs") -> dict:
    p = _providers.get(provider.lower(), _providers["gfs"])
    result = p.get_forecast(location)
    result["disclaimer"] = NWP_DISCLAIMER
    result["location"] = location
    return result


def get_nwp_status() -> dict:
    return {
        "gfs": {"status": "prototype_placeholder", "production_source": "NOAA NOMADS"},
        "wrf": {"status": "prototype_placeholder", "production_source": "WRF-ARW Server"},
        "current_operational": "OpenWeatherMap",
        "disclaimer": NWP_DISCLAIMER,
    }
