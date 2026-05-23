"""
Configurazione centrale della piattaforma.
Legge variabili d'ambiente da .env usando pydantic-settings.
"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Cognitive Assessment Platform"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/cognitive"

    # LLM
    llm_provider: Literal["anthropic", "ollama"] = "anthropic"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    llm_max_retries: int = 3

    # Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "cognitive-audio"

    # Security
    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    access_token_expire_minutes: int = 60 * 24  # 24h


settings = Settings()


def get_llm_provider():
    """Factory che ritorna il provider LLM configurato."""
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY non impostata. "
                "Configurala nel file .env o passa a llm_provider=ollama"
            )
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_retries=settings.llm_max_retries,
        )
    elif settings.llm_provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            max_retries=settings.llm_max_retries,
        )
    else:
        raise ValueError(f"Provider non supportato: {settings.llm_provider}")
