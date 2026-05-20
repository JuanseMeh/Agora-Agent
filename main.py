from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.settings import settings
from db.pool import init_pool, close_pool, init_redis, close_redis
from services.http_client import init_http_clients, close_http_clients
from services.grpc_client import init_grpc_client, close_grpc_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    await init_redis()
    init_http_clients()
    await init_grpc_client()
    yield
    await close_grpc_client()
    await close_http_clients()
    await close_redis()
    await close_pool()


app = FastAPI(
    title="AI Agent Service",
    description="Conversational AI interface for the Agora platform",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    from db.pool import get_pool, get_redis
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    redis_ok = False
    try:
        r = get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "ai-agent",
        "database": db_status,
        "redis": "connected" if redis_ok else "disconnected",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
