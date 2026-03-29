"""
Application configuration — all values loaded from .env file.

Usage:
    from backend.config import settings
    print(settings.DATABASE_URL)
"""

from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Central configuration — all values must be set in .env file."""

    # ── Database ──────────────────────────────────────────────
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "postgres"
    DATABASE_URL: str = "sqlite:///backend/db/local.db"
    SUPABASE_DB_URL: str
        
    # ── LLM ───────────────────────────────────────────────────
    AI_PROVIDER: str = "auto"  # auto | openai | gemini
    OPENAI_API_KEY: str = "dummy-key"
    OPENAI_MODEL: str = "gpt-4o-mini"
    GOOGLE_API_KEY: str = "dummy-key"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    LLM_API_KEY: str = ""  # Legacy override key (optional)
    LLM_MODEL: str = ""  # Legacy override model (optional)

    # ── Retrieval Agent LLM  ──────────────────────────────────
    RETRIEVAL_LLM_PROVIDER: str = ""
    RETRIEVAL_LLM_API_KEY: str = ""
    RETRIEVAL_LLM_MODEL: str = ""

    # ── External Research ─────────────────────────────────────
    TAVILY_API_KEY: str

    # ── Redis / Cache ─────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Application ───────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    APP_ENV: str = "development"
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
