"""
FastAPI application entry-point.

Run with:
    uvicorn backend.main:app --reload
"""

from fastapi import FastAPI

from backend.api.router import api_router


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

    # ── Routes ────────────────────────────────────────────────
    application.include_router(api_router, prefix="/api/v1")

    # ── Health check ──────────────────────────────────────────
    @application.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok"}

    return application


app = create_app()
