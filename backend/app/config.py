"""
Centralized app configuration.

Reads from environment variables / .env file. Keep this the single
source of truth for anything that varies between dev/staging/prod.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[1] is backend/, where .env should live.
# Anchoring to this file's location (instead of a bare ".env") means it's
# found regardless of the working directory uvicorn was launched from.
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    google_api_key: str = ""
    model_name: str = "gemini-2.5-flash"

    database_url: str = ""
    search_api_key: str = ""
    weather_api_key: str = ""
    maps_api_key: str = ""

    secret_key: str = "dev-only-change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()
