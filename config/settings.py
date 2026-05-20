from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # LLM
    google_api_key: str = Field(validation_alias="GOOGLE_API_KEY")
    llm_model: str = Field(validation_alias="LLM_MODEL", default="gemini-2.0-flash")
    llm_temperature: float = Field(validation_alias="LLM_TEMPERATURE", default=0.0)
    llm_max_tokens: int = Field(validation_alias="LLM_MAX_TOKENS", default=4096)

    # Services (Docker container names, not host ports)
    users_service_url: str = Field(
        validation_alias="USERS_SERVICE_URL", default="http://user-service:8080"
    )
    workspace_service_url: str = Field(
        validation_alias="WORKSPACE_SERVICE_URL", default="http://workspace-service:8080"
    )

    # Orchestrator
    orchestrator_grpc_host: str = Field(
        validation_alias="ORCHESTRATOR_GRPC_HOST", default="orchestrator-service"
    )
    orchestrator_grpc_port: int = Field(
        validation_alias="ORCHESTRATOR_GRPC_PORT", default=50051
    )

    # PostgreSQL
    database_url: str = Field(validation_alias="DATABASE_URL")

    # Redis
    redis_url: str = Field(validation_alias="REDIS_URL")
    session_ttl_seconds: int = Field(
        validation_alias="SESSION_TTL_SECONDS", default=3600
    )

    # App
    app_port: int = Field(validation_alias="APP_PORT", default=8000)
    app_env: str = Field(validation_alias="APP_ENV", default="development")
    log_level: str = Field(validation_alias="LOG_LEVEL", default="INFO")
    agent_max_iterations: int = Field(
        validation_alias="AGENT_MAX_ITERATIONS", default=10
    )
    agent_memory_window: int = Field(
        validation_alias="AGENT_MEMORY_WINDOW", default=20
    )


settings = Settings()
