"""
Application configuration — all values loaded from .env file.

Usage:
    from backend.config import settings
    print(settings.DATABASE_URL)
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration — all values must be set in .env file."""

    # ── Database ──────────────────────────────────────────────
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL: str
    # ── LLM ───────────────────────────────────────────────────
    OPENAI_API_KEY: str
    LLM_MODEL: str

    # ── Retrieval Agent LLM  ──────────────────────────────────
    RETRIEVAL_LLM_API_KEY: str
    RETRIEVAL_LLM_MODEL: str

    # ── Redis / Cache ─────────────────────────────────────────
    REDIS_URL: str

    # ── Application ───────────────────────────────────────────
    LOG_LEVEL: str
    APP_ENV: str
    MAX_REPLAN_CYCLES: int = 2
    MAX_PARALLEL_TASKS: int = 4

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }


# Singleton instance — import this wherever config is needed
settings = Settings()
