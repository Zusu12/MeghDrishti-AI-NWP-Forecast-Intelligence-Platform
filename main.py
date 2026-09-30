"""
main.py — MeghDrishti — AI–NWP Forecast Intelligence Platform
Railway-compatible: reads $PORT from environment, binds to 0.0.0.0.
Serves scientific forecasting frontend + all REST and WebSocket API endpoints.
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
from nwp.manager import nwp_manager
from ml.skill_verification import model_skill_service
from ml.weighting_engine import weighting_engine
from ml.confidence_engine import confidence_engine
from ml.extreme_detection import extreme_detector
from ml.forecast_blender import forecast_blender
from services.operational_workflow import workflow_service

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("meghdrishti")

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MeghDrishti starting up…")
    await database.init_db()
    status = config.api_status()
    logger.info(f"API status: {status}")
    if config.DEMO_MODE:
        logger.warning("⚠️  DEMO MODE ACTIVE — set GEMINI_API_KEY and OPENWEATHERMAP_API_KEY for live data.")
    # Start automated background operational blending scheduler
    workflow_service.start_background_scheduler(interval_seconds=10800)
    yield
    logger.info("MeghDrishti shutting down.")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MeghDrishti — AI–NWP Forecast Intelligence Platform",
    description="AI-assisted multi-model NWP forecast blending system — SIH 2026 Problem Statement SIH26081",
    version="2.0.0",
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
        "service": "MeghDrishti — AI–NWP Forecast Intelligence Platform",
        "version": "2.0.0",
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
        loc = location
        if not loc and lat is not None and lon is not None:
            loc = weather.get("location")
        return alert_service.check_alerts(weather, forecast, location=loc)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/alerts/official")
@limiter.limit(config.RATE_LIMIT_WEATHER)
async def get_official_alerts(
    request: Request,
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    try:
        import imd_service
        return await imd_service.get_official_imd_warnings(location=location, lat=lat, lon=lon)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/ingestion/status")
async def get_ingestion_status():
    return ingestion_service.ingestion_service.get_detailed_telemetry()


@app.post("/ingestion/mqtt/publish")
async def publish_mqtt(payload: dict, topic: str = "weather/stations/manual/telemetry"):
    return ingestion_service.ingestion_service.publish_mqtt_telemetry(topic, payload)


@app.post("/ingestion/wis2/publish")
async def publish_wis2(wnm: dict, topic: str = "origin/a/wis2/in-imd/data/core/weather/surface-based-observations/synop"):
    return ingestion_service.ingestion_service.publish_wis2_wnm(topic, wnm)


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
async def get_nwp(
    location: Optional[str] = "Visakhapatnam",
    provider: str = "owm",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    try:
        return await nwp_service.get_nwp_forecast(
            location=location or "Visakhapatnam",
            provider=provider,
            lat=lat,
            lon=lon,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/nwp/status")
async def nwp_status():
    return nwp_service.get_nwp_status()


# ── SIH 2026 Problem Statement SIH26081 Endpoints ──────────────────────────────

@app.get("/api/weather/current")
@limiter.limit(config.RATE_LIMIT_WEATHER)
async def api_get_current(
    request: Request,
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """Observational reference ground truth from OpenWeatherMap."""
    return await get_current(request=request, location=location, lat=lat, lon=lon)


@app.get("/api/forecast")
@limiter.limit(config.RATE_LIMIT_WEATHER)
async def api_get_forecast(
    request: Request,
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """Observation-based multi-day baseline forecast."""
    return await get_forecast(request=request, location=location, lat=lat, lon=lon)


@app.get("/api/nwp/models")
async def api_nwp_models():
    """List registered NWP models and capabilities (GFS, WRF, ECMWF, Demo)."""
    return {
        "models": nwp_manager.get_available_models(),
        "disclaimer": "Numerical Weather Prediction Model Layer — Independent physical simulations.",
    }


@app.get("/api/nwp/forecast")
async def api_nwp_model_forecast(
    model: str = "GFS",
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """Retrieve normalized forecast from an individual NWP model."""
    series = await nwp_manager.fetch_model_forecast(model_name=model, location=location, lat=lat, lon=lon)
    if not series:
        raise HTTPException(status_code=503, detail=f"Model provider '{model}' unavailable.")
    return series.model_dump()


@app.get("/api/nwp/compare")
async def api_nwp_compare(
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """Side-by-side comparison across all NWP models and consensus blend."""
    series_map, health = await nwp_manager.fetch_all_models(location=location, lat=lat, lon=lon)
    if not series_map:
        raise HTTPException(status_code=503, detail="No NWP models currently reachable.")
    
    blended = forecast_blender.blend_forecasts(series_map)
    return {
        "location": location,
        "models_available": list(series_map.keys()),
        "provider_health": health,
        "individual_models": {m: s.model_dump() for m, s in series_map.items()},
        "blended_consensus": blended.model_dump(),
    }


@app.get("/api/nwp/blended")
async def api_nwp_blended(
    location: Optional[str] = "Visakhapatnam",
    lat: Optional[float] = None,
    lon: Optional[float] = None,
):
    """Consensus blended forecast combining GFS, WRF, and ECMWF with dynamic weights."""
    series_map, _ = await nwp_manager.fetch_all_models(location=location, lat=lat, lon=lon)
    if not series_map:
        raise HTTPException(status_code=503, detail="Unable to retrieve NWP forecasts for blending.")
    blended = forecast_blender.blend_forecasts(series_map)
    return blended.model_dump()


@app.get("/api/nwp/weights")
async def api_nwp_weights(
    variable: str = "temperature",
    lead_time_hours: int = 24,
    region: str = "coastal_ap",
    season: str = "monsoon",
    weather_regime: str = "normal",
):
    """Dynamic model weights for a specific variable and atmospheric situation."""
    weights_res = weighting_engine.compute_weights(
        available_models=["GFS", "WRF", "ECMWF"],
        variable=variable,
        lead_time_hours=lead_time_hours,
        region=region,
        season=season,
        weather_regime=weather_regime,
    )
    return weights_res.model_dump()


@app.get("/api/nwp/weight-map")
async def api_nwp_weight_map(
    variable: str = "temperature",
    lead_time_hours: int = 24,
    season: str = "monsoon",
    weather_regime: str = "normal",
):
    """Spatial model weight distribution across Indian meteorological subdivisions."""
    return weighting_engine.generate_weight_map(
        variable=variable,
        lead_time_hours=lead_time_hours,
        season=season,
        weather_regime=weather_regime,
    )


@app.get("/api/nwp/confidence")
async def api_nwp_confidence(
    location: Optional[str] = "Visakhapatnam",
    lead_time_hours: int = 24,
):
    """Confidence score and uncertainty analysis for consensus forecast."""
    series_map, _ = await nwp_manager.fetch_all_models(location=location)
    if not series_map:
        raise HTTPException(status_code=503, detail="NWP models unreachable.")
    blended = forecast_blender.blend_forecasts(series_map)
    pt = next((p for p in blended.forecast_points if p.lead_time_hours == lead_time_hours), blended.forecast_points[0])
    return pt.confidence.model_dump()


@app.get("/api/nwp/disagreement")
async def api_nwp_disagreement(
    location: Optional[str] = "Visakhapatnam",
    lead_time_hours: int = 24,
):
    """Inter-model spread, range, and variance."""
    series_map, _ = await nwp_manager.fetch_all_models(location=location)
    if not series_map:
        raise HTTPException(status_code=503, detail="NWP models unreachable.")
    blended = forecast_blender.blend_forecasts(series_map)
    pt = next((p for p in blended.forecast_points if p.lead_time_hours == lead_time_hours), blended.forecast_points[0])
    return {
        "lead_time_hours": pt.lead_time_hours,
        "spread_sigma": pt.confidence.disagreement_spread,
        "inter_model_range": pt.confidence.inter_model_range,
        "agreement_score": pt.confidence.agreement_score,
        "individual_model_values": pt.individual_models,
    }


@app.get("/api/nwp/skill")
async def api_nwp_skill(
    model: str = "GFS",
    region: str = "coastal_ap",
    season: str = "monsoon",
    variable: str = "temperature",
    lead_time: int = 24,
):
    """Historical skill metrics (MAE, RMSE, Bias, CSI) for a specific model."""
    skill = model_skill_service.get_skill(
        model_name=model,
        region=region,
        season=season,
        variable=variable,
        lead_time_hours=lead_time,
    )
    if not skill:
        return {"message": "Historical verification data unavailable for configuration."}
    return skill.model_dump()


@app.get("/api/nwp/verification")
async def api_nwp_verification(
    variable: str = "temperature",
    region: str = "coastal_ap",
    season: str = "monsoon",
    lead_time: int = 24,
):
    """Verification comparison contrasting single models vs Blended Consensus."""
    comp = model_skill_service.compare_models(
        variable=variable,
        region=region,
        season=season,
        lead_time_hours=lead_time,
    )
    return comp.model_dump()


@app.get("/api/extreme-weather")
async def api_extreme_weather(
    location: Optional[str] = "Visakhapatnam",
):
    """Model-based extreme weather risk indicators from consensus forecasts."""
    series_map, _ = await nwp_manager.fetch_all_models(location=location)
    if not series_map:
        raise HTTPException(status_code=503, detail="NWP models unreachable.")
    blended = forecast_blender.blend_forecasts(series_map)
    all_alerts = []
    for pt in blended.forecast_points:
        all_alerts.extend([a.model_dump() for a in pt.extreme_alerts])
    return {
        "location": location,
        "overall_summary": blended.extreme_risk_summary,
        "active_alerts_count": len(all_alerts),
        "alerts": all_alerts,
        "disclaimer": (
            "MODEL-BASED RISK GUIDANCE — Generated algorithmically by multi-model NWP consensus. "
            "Not an official government warning. Refer to IMD/NDMA for statutory alerts."
        ),
    }


@app.get("/api/workflow/status")
async def api_workflow_status():
    """Execution status and telemetry of the operational blending pipeline."""
    return workflow_service.get_status().model_dump()


@app.post("/api/workflow/run")
async def api_workflow_run(
    location: Optional[str] = "Visakhapatnam",
):
    """Manually trigger an operational forecast blending cycle."""
    status, _ = await workflow_service.execute_blending_cycle(location=location, execution_type="MANUAL_TRIGGER")
    return status.model_dump()


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
        # 1. Check if path exists inside static_dir (e.g. "styles.css", "app.js")
        candidate = os.path.join(static_dir, path)
        if os.path.isfile(candidate):
            return FileResponse(candidate)
        # 2. Check if path has "static/" prefix stripped (e.g. "/static/styles.css")
        if path.startswith("static/"):
            sub_candidate = os.path.join(static_dir, path[len("static/"):])
            if os.path.isfile(sub_candidate):
                return FileResponse(sub_candidate)
        # 3. SPA fallback — return index.html
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
