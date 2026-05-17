from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM
    google_api_key: str | None = None
    llm_model: str = "gemini-2.0-flash"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096

    # Services
    users_service_url: str = "http://users-service:8001"
    workspace_service_url: str = "http://workspace-service:8002"

    # Orchestrator
    orchestrator_grpc_host: str = "orchestrator-service"
    orchestrator_grpc_port: int = 50051

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://agent:agent@agent-db:5432/agent"

    # Redis
    redis_url: str = "redis://agent-redis:6379/0"
    session_ttl_seconds: int = 3600

    # App
    app_port: int = 8000
    app_env: str = "development"
    log_level: str = "INFO"
    agent_max_iterations: int = 10

settings = Settings()
