from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

# .env lives in the project root (two levels above this file: app/ -> backend/ -> root)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # App
    app_name: str = "Persona AI Studio"
    app_version: str = "1.0.0"
    debug: bool = False

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "persona_ai_studio"

    # Gemini (primary AI provider)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Groq (fallback AI provider — free tier)
    groq_api_key: str = ""
    groq_model: str = "groq/compound-mini"

    # CORS
    cors_origins: list[str] = ["http://localhost:8000"]

    # Auth
    admin_username: str = "admin"
    admin_password: str = "admin123"
    jwt_secret: str = "change-me-in-production"
    jwt_expiry_hours: int = 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
