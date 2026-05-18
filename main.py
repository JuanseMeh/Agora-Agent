from fastapi import FastAPI
from contextlib import asynccontextmanager
from config.settings import settings
from db.pool import init_pool, close_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()

app = FastAPI(
    title="AI Agent Service",
    description="Conversational AI interface for the Agora platform",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health_check():
    from db.pool import get_pool
    # Simple check to see if pool is accessible
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {"status": "ok", "service": "ai-agent", "database": db_status}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
