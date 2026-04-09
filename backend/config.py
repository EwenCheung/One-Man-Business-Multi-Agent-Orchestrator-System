"""
Application configuration — all values loaded from .env file.

Usage:
    from backend.config import settings
    print(settings.SUPABASE_DB_URL)
"""

from pydantic_settings import BaseSettings

from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Central configuration — all values must be set in .env file."""

    # ── Database (Supabase — unified) ────────────────────────
    SUPABASE_DB_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    OWNER_ID: str = "4c116430-f683-4a8a-91f7-546fa8bc5d76"

    # ── LLM ───────────────────────────────────────────────────
    AI_PROVIDER: str = "auto"  # auto | openai | gemini
    OPENAI_API_KEY: str = "dummy-key"
    OPENAI_MODEL: str = "gpt-4o-mini"
    GOOGLE_API_KEY: str = "dummy-key"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    LLM_API_KEY: str = ""  # Legacy override key (optional)
    LLM_MODEL: str = ""  # Legacy override model (optional)

    # ── Retrieval Agent LLM  ──────────────────────────────────
    RETRIEVAL_LLM_PROVIDER: str | None = None
    RETRIEVAL_LLM_API_KEY: str | None = None
    RETRIEVAL_LLM_MODEL: str | None = None

    # ── Policy Agent LLM ──────────────────────────────────────
    POLICY_LLM_PROVIDER: str | None = None
    POLICY_LLM_API_KEY: str | None = None
    POLICY_LLM_MODEL: str | None = None

    # ── Policy Agent RAG ──────────────────────────────────────
    EMBEDDING_MODEL: str = "text-embedding-3-small"  # 1536 dims — matches Vector(1536)
    POLICY_CHUNK_SIZE: int = 2000  # characters per chunk (~500 tokens)
    POLICY_CHUNK_OVERLAP: int = 200  # overlap between consecutive chunks
    POLICY_TOP_K: int = 10  # chunks retrieved from pgvector before reranking
    POLICY_TOP_N: int = 5  # chunks kept after reranking
    RERANKER_MODEL: str = "mixedbread-ai/mxbai-rerank-base-v1"
    HF_TOKEN: str = ""  # optional — avoids HuggingFace Hub rate limits

    # ── Retrieval Agent RAG ───────────────────────────────────
    BUSINESS_TOP_K: int = 10  # rows returned from business data semantic search

    # ── External Research ─────────────────────────────────────
    TAVILY_API_KEY: str = ""

    # ── Redis / Cache ─────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Application ───────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    APP_ENV: str = "development"
    INTERNAL_API_KEY: str = ""
    AUTO_CREATE_SUPABASE_AUTH_USERS: bool = False
    MAX_REPLAN_CYCLES: int = 2
    MAX_PARALLEL_TASKS: int = 4
    BACKEND_PUBLIC_URL: str = ""

    # ── Observability ─────────────────────────────────────────
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


# Singleton instance — import this wherever config is needed
settings = Settings()
