from fastapi import FastAPI
from config.settings import settings

app = FastAPI(
    title="AI Agent Service",
    description="Conversational AI interface for the Agora platform",
    version="0.1.0",
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ai-agent"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
