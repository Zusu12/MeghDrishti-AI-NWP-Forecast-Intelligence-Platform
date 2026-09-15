"""
main.py — WeatherGPT FastAPI application
Railway-compatible: reads $PORT from environment, binds to 0.0.0.0.
Serves static frontend + all REST and WebSocket API endpoints.
"""
import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

import config
import database
import gemini_service
import weather_service
import alert_service
import advisory_service
import translation_service
import historical_service
import nwp_service
import elevenlabs_service
import ingestion_service

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("weathergpt")

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WeatherGPT starting up…")
    await database.init_db()
    status = config.api_status()
    logger.info(f"API status: {status}")
    if config.DEMO_MODE:
        logger.warning("⚠️  DEMO MODE ACTIVE — set GEMINI_API_KEY and OPENWEATHERMAP_API_KEY for live data.")
    yield
    logger.info("WeatherGPT shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="WeatherGPT",
    description="AI-powered multilingual weather intelligence — SIH 2026 Prototype",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    language: str = Field("en", pattern="^(en|hi|te)$")
    session_id: Optional[str] = None
    location: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    location: Optional[str]
    weather: Optional[dict]
    forecast: Optional[list]
    alerts: Optional[dict]
    intent: Optional[dict]
    language: str
    demo_mode: bool
    latency: dict


class VoiceRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=600)
    language: str = Field("en", pattern="^(en|hi|te)$")


class AdvisoryRequest(BaseModel):
    location: str = Field(..., min_length=1, max_length=100)
    mode: str = Field(..., pattern="^(agriculture|aviation|marine|travel|outdoor|urban)$")
    language: Optional[str] = Field("en", pattern="^(en|hi|te)$")


# ── WebSocket alert connections ────────────────────────────────────────────────
class AlertConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


alert_manager = AlertConnectionManager()


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "WeatherGPT",
        "version": "1.0.0",
        "apis": config.api_status(),
        "ingestion": ingestion_service.ingestion_service.get_status(),
    }


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(config.RATE_LIMIT_CHAT)
async def chat(request: Request, body: ChatRequest):
    t_total = time.perf_counter()
    session_id = body.session_id or str(uuid.uuid4())
    lang = body.language
    raw_message = body.message.strip()

    latency: dict[str, int] = {}

    # 1. Detect language from message script if non-English
    detected_lang = translation_service.detect_language(raw_message)
    if detected_lang != "en":
        lang = detected_lang

    # 2. Translate to English for intent extraction
    t0 = time.perf_counter()
    english_query = translation_service.translate_to_english(raw_message, lang)
    latency["translation_in_ms"] = round((time.perf_counter() - t0) * 1000)

    # 3. Parse intent with Gemini
    t0 = time.perf_counter()
    intent = await gemini_service.parse_intent(english_query)
    latency["gemini_intent_ms"] = round((time.perf_counter() - t0) * 1000)

    # 4. Resolve location or coordinates
    location = intent.get("location") or body.location or "Visakhapatnam"
    use_coords = (body.lat is not None and body.lon is not None and not intent.get("location"))

    # 5. Fetch weather
    weather, forecast = None, []
    try:
        t0 = time.perf_counter()
        if use_coords:
            weather = await weather_service.get_current_weather(lat=body.lat, lon=body.lon)
            forecast = await weather_service.get_forecast(lat=body.lat, lon=body.lon)
        else:
            weather = await weather_service.get_current_weather(location=location)
            forecast = await weather_service.get_forecast(location=location)
        latency["weather_ms"] = round((time.perf_counter() - t0) * 1000)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 6. Alert analysis
    alerts = alert_service.check_alerts(weather, forecast)

    # Broadcast to WebSocket clients if HIGH alert
    if alerts.get("severity") in ("WARNING", "HIGH"):
        asyncio.create_task(alert_manager.broadcast({
            "type": "alert",
            "location": weather.get("location", location),
            "severity": alerts["severity"],
            "alerts": alerts["alerts"],
        }))

    # 7. Generate Gemini response (directly in requested language)
    t0 = time.perf_counter()
    advisory_mode = intent.get("advisory_mode")
    raw_response = await gemini_service.generate_response(
        query=english_query,
        weather=weather,
        forecast=forecast,
        intent=intent,
        advisory_mode=advisory_mode,
        language=lang,
    )
    latency["gemini_response_ms"] = round((time.perf_counter() - t0) * 1000)

    # 8. If Gemini returned English despite requested non-English, fallback translate
    final_response = raw_response
    resp_detected = translation_service.detect_language(raw_response)
    if lang != "en" and resp_detected == "en":
        t0 = time.perf_counter()
        final_response = translation_service.translate_from_english(raw_response, lang)
        latency["translation_out_ms"] = round((time.perf_counter() - t0) * 1000)
    else:
        latency["translation_out_ms"] = 0

    latency["total_ms"] = round((time.perf_counter() - t_total) * 1000)

    # Log
    resolved_loc = weather.get("location", location)
    logger.info(
        f"CHAT | loc={resolved_loc} | lang={lang} | total={latency['total_ms']}ms | "
        f"weather={latency.get('weather_ms')}ms | gemini={latency.get('gemini_response_ms')}ms"
    )

    # Persist
    await database.save_message(session_id, "user", raw_message, lang)
    await database.save_message(session_id, "assistant", final_response, lang)
    await database.log_query(
        raw_message, resolved_loc, intent.get("type"), lang, latency["total_ms"]
    )

    return ChatResponse(
        response=final_response,
        location=resolved_loc,
        weather=weather,
        forecast=forecast[:8],  # Next 24h intervals
        alerts=alerts,
        intent=intent,
        language=lang,
        demo_mode=config.DEMO_MODE,
        latency=latency,
    )


@app.get("/weather/current")
@limiter.limit(config.RATE_LIMIT_WEATHER)
async def get_current(
    request: Request,
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    try:
        if lat is not None and lon is not None:
            return await weather_service.get_current_weather(lat=lat, lon=lon)
        return await weather_service.get_current_weather(location=location)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/weather/forecast")
@limiter.limit(config.RATE_LIMIT_WEATHER)
async def get_forecast(
    request: Request,
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    try:
        if lat is not None and lon is not None:
            return await weather_service.get_forecast(lat=lat, lon=lon)
        return await weather_service.get_forecast(location=location)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/alerts")
@limiter.limit(config.RATE_LIMIT_WEATHER)
async def get_alerts(
    request: Request,
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    try:
        if lat is not None and lon is not None:
            weather = await weather_service.get_current_weather(lat=lat, lon=lon)
            forecast = await weather_service.get_forecast(lat=lat, lon=lon)
        else:
            weather = await weather_service.get_current_weather(location=location)
            forecast = await weather_service.get_forecast(location=location)
        return alert_service.check_alerts(weather, forecast)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/climate")
async def get_climate(location: str = "Visakhapatnam", days: int = 30):
    days = max(7, min(90, days))
    return historical_service.get_historical_weather(location, days=days)


@app.get("/location")
async def search_location(q: str = "Visakhapatnam"):
    try:
        return await weather_service.get_current_weather(location=q)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/advisory")
@limiter.limit(config.RATE_LIMIT_CHAT)
async def get_advisory(request: Request, body: AdvisoryRequest):
    result = await advisory_service.get_advisory(body.location, body.mode, language=body.language or "en")
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@app.post("/voice")
@limiter.limit(config.RATE_LIMIT_VOICE)
async def voice(request: Request, body: VoiceRequest):
    """
    Generate speech from text using ElevenLabs.
    Returns MP3 audio. Falls back with 503 if ElevenLabs is unavailable
    so the frontend can use browser speechSynthesis instead.
    """
    try:
        audio_bytes = await elevenlabs_service.text_to_speech(body.text, body.language)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except RuntimeError as e:
        # Return 503 so frontend gracefully uses browser speechSynthesis fallback
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/nwp")
async def get_nwp(location: str = "Visakhapatnam", provider: str = "gfs"):
    return nwp_service.get_nwp_forecast(location, provider)


@app.get("/nwp/status")
async def nwp_status():
    return nwp_service.get_nwp_status()


@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await alert_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; alerts are pushed from chat endpoint
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)


# ── Static frontend ────────────────────────────────────────────────────────────
# Must come AFTER all API routes so API endpoints are not intercepted
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def root():
        return FileResponse(os.path.join(static_dir, "index.html"))

    @app.get("/{path:path}")
    async def catch_all(path: str):
        # SPA fallback — always return index.html
        return FileResponse(os.path.join(static_dir, "index.html"))


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=config.DEBUG,
        log_level="debug" if config.DEBUG else "info",
    )
