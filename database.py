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

# On Vercel / Serverless, the app root is read-only; use writable /tmp for SQLite
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DB_PATH = Path(tempfile.gettempdir()) / "weathergpt.db"
else:
    DB_PATH = Path(__file__).parent / "weathergpt.db"


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
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES)
        await db.commit()


async def save_message(session_id: str, role: str, content: str, language: str = "en") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO conversations (session_id, role, content, language, created_at) VALUES (?,?,?,?,?)",
            (session_id, role, content, language, time.time()),
        )
        await db.commit()


async def get_history(session_id: str, limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content, language, created_at FROM conversations "
            "WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in reversed(rows)]


async def log_query(query, location, intent_type, language, latency_ms) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO query_history (query, location, intent_type, language, latency_ms, created_at) VALUES (?,?,?,?,?,?)",
            (query, location, intent_type, language, latency_ms, time.time()),
        )
        await db.commit()


async def cache_get(key: str):
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


async def cache_set(key: str, data, ttl: int = 300) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO weather_cache (cache_key, data, expires_at) VALUES (?,?,?)",
            (key, json.dumps(data), time.time() + ttl),
        )
        await db.commit()
