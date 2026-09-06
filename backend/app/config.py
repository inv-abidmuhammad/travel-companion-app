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

    # Bare psycopg-style DSN, e.g. "postgresql://user:pass@host:5432/db" —
    # this is the form both langgraph-checkpoint-postgres AND (via the
    # property below) SQLAlchemy can use, from one setting.
    database_url: str = ""

    search_api_key: str = ""
    weather_api_key: str = ""
    maps_api_key: str = ""

    secret_key: str = "dev-only-change-me"

    @property
    def sqlalchemy_database_url(self) -> str:
        """SQLAlchemy needs a dialect+driver prefix to pick psycopg3
        specifically (plain "postgresql://" would default to psycopg2,
        which isn't installed here — psycopg3 is, since the LangGraph
        checkpointer needs it too). langgraph-checkpoint-postgres, on
        the other hand, wants the bare DSN with no "+psycopg" suffix —
        confirmed directly: it raises a connection-string parse error
        if given one. Hence: one setting, two derived forms.
        """
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()

