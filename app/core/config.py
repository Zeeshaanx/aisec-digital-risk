"""
Application configuration using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──
    APP_NAME: str = "Media Intelligence API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/media_intel"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/media_intel"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30

    # ── API Keys ──
    OPENAI_API_KEY: str = ""

    # ── SearXNG Search ──
    SEARXNG_URL: str = "http://searxng:8080/"
    SEARXNG_QUERY_DELAY: float = 2
    SEARXNG_MAX_PAGES: int = 2

    # ── LLM ──
    LLM_MODEL: str = "gpt-5-mini"
    INPUT_COST_PER_1K: float = 0.00025
    OUTPUT_COST_PER_1K: float = 0.002

    # ── Scan Defaults ──
    MAX_CONCURRENCY: int = 3
    MAX_CONTENT_CHARS: int = 50_000

    # ── Feature: LLM Target Matching ──
    ENABLE_LLM_TARGET_MATCHING: bool = True
    TARGET_MATCH_THRESHOLD: float = 0.85
    TARGET_MATCH_MAX_CANDIDATES: int = 50

    # ── Feature: Smart Scan Caching ──
    ENABLE_SCAN_CACHING: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
