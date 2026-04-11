"""
FastAPI application entry-point.

Run with:
    uvicorn backend.main:app --reload
"""

from fastapi import FastAPI

from backend.api import purchase_router
from backend.api.router import api_router
from backend.config import settings
from backend.integrations.telegram_webhook import telegram_router


def create_app() -> FastAPI:
    """Application factory."""
    application = FastAPI(
        title="Multi-Agent Orchestrator",
        description=(
            "A role-aware multi-agent auto-reply system with structured memory, "
            "retrieval, and risk-controlled planning."
        ),
        version="0.1.0",
    )

    application.state.internal_api_key = settings.INTERNAL_API_KEY
    application.state.app_env = settings.APP_ENV

    # ── Routes ────────────────────────────────────────────────
    application.include_router(api_router, prefix="/api/v1")
    application.include_router(purchase_router, prefix="/api/v1")
    application.include_router(telegram_router, prefix="/api/v1/telegram")

    # ── Health check ──────────────────────────────────────────
    @application.get("/", tags=["system"])
    async def root():
        return {
            "service": "Multi-Agent Orchestrator",
            "status": "ok",
            "health": "/health",
            "docs": "/docs",
        }

    @application.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok"}

    return application


app = create_app()
