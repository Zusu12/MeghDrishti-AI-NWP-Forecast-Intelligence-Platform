"""
historical_service.py — Climate/historical weather abstraction
⚠️ DEMO HISTORICAL DATA — Not actual historical observations.
"""
import math
import random
from datetime import datetime, timedelta

DEMO_LABEL = "⚠️ DEMO HISTORICAL DATA — Not actual historical observations"


def get_historical_weather(location: str, start_date: str = None, end_date: str = None, days: int = 30) -> dict:
    """Return demo historical weather data for visualisation."""
    if start_date and end_date:
        try:
            s = datetime.fromisoformat(start_date)
            e = datetime.fromisoformat(end_date)
            days = max(7, min(365, (e - s).days))
        except ValueError:
            pass

    random.seed(hash(location.lower()) % 1000)
    base_date = datetime.now() - timedelta(days=days)
    base_temp = 28 + (random.random() * 6 - 3)

    dates, temps, rainfall, humidity = [], [], [], []
    for i in range(days):
        d = base_date + timedelta(days=i)
        dates.append(d.strftime("%Y-%m-%d"))
        t = base_temp + 3 * math.sin(i / 7 * math.pi) + random.gauss(0, 1.5)
        temps.append(round(t, 1))
        rain = max(0, random.gauss(2, 5)) if random.random() < 0.3 else 0
        rainfall.append(round(rain, 1))
        hum = max(40, min(95, 70 + random.gauss(0, 10)))
        humidity.append(round(hum, 1))

    return {
        "location": location,
        "period_days": days,
        "dates": dates,
        "temperature": temps,
        "rainfall": rainfall,
        "humidity": humidity,
        "stats": {
            "avg_temp": round(sum(temps) / len(temps), 1),
            "max_temp": max(temps),
            "min_temp": min(temps),
            "total_rainfall": round(sum(rainfall), 1),
            "avg_humidity": round(sum(humidity) / len(humidity), 1),
        },
        "label": DEMO_LABEL,
        "demo": True,
    }
