"""
ingestion_service.py — Meteorological Data Ingestion Abstraction
Supports: REST API (active), WebSocket, MQTT, WIS2.0 (integration-ready stubs).
Production: plug in real meteorological feeds without changing the consumer interface.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DataSource(ABC):
    """Abstract meteorological data source."""
    name: str = "base"
    status: str = "inactive"

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def fetch(self, location: str) -> dict: ...

    @abstractmethod
    async def disconnect(self) -> None: ...


class OpenWeatherRESTSource(DataSource):
    """Active source: OpenWeatherMap REST API."""
    name = "OpenWeatherMap REST"
    status = "active"

    async def connect(self) -> bool:
        import config
        return bool(config.OWM_API_KEY)

    async def fetch(self, location: str) -> dict:
        import weather_service
        return await weather_service.get_current_weather(location)

    async def disconnect(self) -> None:
        pass  # Stateless REST


class WebSocketSource(DataSource):
    """Integration-ready: WebSocket meteorological data feed."""
    name = "WebSocket Feed"
    status = "integration_ready"

    async def connect(self) -> bool:
        logger.info("WebSocket source: integration-ready placeholder")
        return False

    async def fetch(self, location: str) -> dict:
        raise NotImplementedError("WebSocket source not configured for this prototype.")

    async def disconnect(self) -> None:
        pass


class MQTTSource(DataSource):
    """Integration-ready: MQTT meteorological sensor feed."""
    name = "MQTT Feed"
    status = "integration_ready"

    async def connect(self) -> bool:
        logger.info("MQTT source: integration-ready placeholder")
        return False

    async def fetch(self, location: str) -> dict:
        raise NotImplementedError("MQTT source not configured for this prototype.")

    async def disconnect(self) -> None:
        pass


class WIS2Source(DataSource):
    """Integration-ready: WMO WIS2.0 global weather data broker."""
    name = "WIS2.0"
    status = "integration_ready"

    async def connect(self) -> bool:
        logger.info("WIS2.0 source: integration-ready placeholder")
        return False

    async def fetch(self, location: str) -> dict:
        raise NotImplementedError("WIS2.0 source not configured for this prototype.")

    async def disconnect(self) -> None:
        pass


class DataIngestionService:
    """
    Unified ingestion layer.
    Tries sources in priority order, falls back to next available.
    """
    def __init__(self):
        self._sources: list[DataSource] = [
            OpenWeatherRESTSource(),
            WebSocketSource(),
            MQTTSource(),
            WIS2Source(),
        ]

    async def ingest(self, location: str) -> dict:
        for source in self._sources:
            if source.status == "active":
                try:
                    data = await source.fetch(location)
                    data["_source"] = source.name
                    return data
                except Exception as e:
                    logger.error(f"Source {source.name} failed: {e}")
        raise RuntimeError("All data sources failed. Cannot retrieve weather data.")

    def get_status(self) -> list[dict]:
        return [
            {"name": s.name, "status": s.status}
            for s in self._sources
        ]


# Module-level singleton
ingestion_service = DataIngestionService()
