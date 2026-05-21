from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.settings import settings
from db.pool import close_pool, close_redis, get_pool, init_pool, init_redis
from services.grpc_client import close_grpc_client, init_grpc_client
from services.http_client import close_http_clients, init_http_clients

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ai-agent (env=%s)", settings.app_env)
    await init_pool()
    await init_redis()
    init_http_clients()
    await init_grpc_client()
    logger.info("All clients initialized")
    yield
    await close_grpc_client()
    await close_http_clients()
    await close_redis()
    await close_pool()
    logger.info("All clients closed")


app = FastAPI(
    title="Agora AI Agent",
    version="0.1.0",
    lifespan=lifespan,
)

from api.routes import router  # noqa: E402
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    db_status = "connected"
    redis_status = "connected"

    try:
        pool = get_pool()
        await pool.fetchval("SELECT 1")
    except Exception:
        db_status = "error"

    try:
        from db.pool import get_redis
        redis = get_redis()
        await redis.ping()
    except Exception:
        redis_status = "error"

    return {
        "status": "ok",
        "database": db_status,
        "redis": redis_status,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
