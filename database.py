"""
database.py — WeatherGPT SQLite persistence layer
Tables: conversations, query_history, weather_cache
Designed for easy PostgreSQL migration — only standard SQL used.
"""
import asyncio
import json
import os
import tempfile
import time
import aiosqlite
from pathlib import Path

def _resolve_db_path():
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return Path(tempfile.gettempdir()) / "meghdrishti.db"
    try:
        test_file = Path(__file__).parent / ".write_test"
        test_file.touch()
        test_file.unlink()
        return Path(__file__).parent / "meghdrishti.db"
    except Exception:
        return Path(tempfile.gettempdir()) / "meghdrishti.db"

DB_PATH = _resolve_db_path()


CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    language    TEXT DEFAULT 'en',
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS query_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query       TEXT NOT NULL,
    location    TEXT,
    intent_type TEXT,
    language    TEXT DEFAULT 'en',
    latency_ms  INTEGER,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS weather_cache (
    cache_key   TEXT PRIMARY KEY,
    data        TEXT NOT NULL,
    expires_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS forecast_models (
    model_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    institution TEXT NOT NULL,
    resolution  TEXT,
    is_active   INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS model_skill (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name  TEXT NOT NULL,
    region      TEXT NOT NULL,
    season      TEXT NOT NULL,
    variable    TEXT NOT NULL,
    lead_time   INTEGER NOT NULL,
    mae         REAL NOT NULL,
    rmse        REAL NOT NULL,
    bias        REAL NOT NULL,
    csi         REAL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS model_weights (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    location    TEXT NOT NULL,
    variable    TEXT NOT NULL,
    lead_time   INTEGER NOT NULL,
    weights_json TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS blended_forecasts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    location    TEXT NOT NULL,
    cycle_time  TEXT NOT NULL,
    data_json   TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id      TEXT PRIMARY KEY,
    status      TEXT NOT NULL,
    total_ms    INTEGER NOT NULL,
    details_json TEXT NOT NULL,
    created_at  REAL NOT NULL
);
"""


async def init_db() -> None:
    global DB_PATH
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executescript(CREATE_TABLES)
            await db.commit()
    except Exception:
        try:
            DB_PATH = Path(tempfile.gettempdir()) / "meghdrishti.db"
            async with aiosqlite.connect(DB_PATH) as db:
                await db.executescript(CREATE_TABLES)
                await db.commit()
        except Exception:
            DB_PATH = ":memory:"
            async with aiosqlite.connect(DB_PATH) as db:
                await db.executescript(CREATE_TABLES)
                await db.commit()


async def save_message(session_id: str, role: str, content: str, language: str = "en") -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO conversations (session_id, role, content, language, created_at) VALUES (?,?,?,?,?)",
                (session_id, role, content, language, time.time()),
            )
            await db.commit()
    except Exception:
        pass


async def get_history(session_id: str, limit: int = 20) -> list:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT role, content, language, created_at FROM conversations "
                "WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in reversed(rows)]
    except Exception:
        return []


async def log_query(query, location, intent_type, language, latency_ms) -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO query_history (query, location, intent_type, language, latency_ms, created_at) VALUES (?,?,?,?,?,?)",
                (query, location, intent_type, language, latency_ms, time.time()),
            )
            await db.commit()
    except Exception:
        pass


async def cache_get(key: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT data, expires_at FROM weather_cache WHERE cache_key=?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        data, expires_at = row
        if time.time() > expires_at:
            return None
        return json.loads(data)
    except Exception:
        return None


async def cache_set(key: str, data, ttl: int = 300) -> None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO weather_cache (cache_key, data, expires_at) VALUES (?,?,?)",
                (key, json.dumps(data), time.time() + ttl),
            )
            await db.commit()
    except Exception:
        pass
