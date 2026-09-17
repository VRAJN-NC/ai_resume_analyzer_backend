from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # ignore docker-only vars like POSTGRES_USER/PASSWORD/DB
    )

    # Database
    database_url: str

    # OpenAI - never logged or exposed in responses
    openai_api_key: str

    # JWT - never logged or exposed in responses
    jwt_secret_key: str
    jwt_expire_minutes: int = 60

    # CORS
    allowed_origin: str = "http://localhost:3000"

    # App
    environment: str = "development"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()
