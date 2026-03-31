"""
API Router — REST endpoints for the orchestrator.

Endpoints:
  POST  /api/v1/messages/incoming       → run the pipeline
  GET   /api/v1/messages/{thread_id}    → thread history (stub)
  POST  /api/v1/memory/approve/{id}     → approve memory proposal
  POST  /api/v1/memory/reject/{id}      → reject memory proposal
  POST  /api/v1/replies/approve/{id}    → approve held reply
  POST  /api/v1/replies/reject/{id}     → reject held reply
  GET   /api/v1/dashboard/summary       → dashboard data (stub)
"""

from fastapi import APIRouter

from backend.models import IncomingMessage, PipelineResult
from backend.services.approval_service import (
    approve_memory,
    reject_memory,
    approve_reply,
    reject_reply,
)

api_router = APIRouter(tags=["orchestrator"])


# ─── Memory Approval ──────────────────────────────────────────────

@api_router.post("/memory/approve/{proposal_id}")
def approve_memory_endpoint(proposal_id: str):
    approve_memory(proposal_id)
    return {"ok": True}


@api_router.post("/memory/reject/{proposal_id}")
def reject_memory_endpoint(proposal_id: str):
    reject_memory(proposal_id)
    return {"ok": True}


# ─── Reply Approval ───────────────────────────────────────────────

@api_router.post("/replies/approve/{held_reply_id}")
def approve_reply_endpoint(held_reply_id: str):
    result = approve_reply(held_reply_id)
    return result


@api_router.post("/replies/reject/{held_reply_id}")
def reject_reply_endpoint(held_reply_id: str, reason: str = ""):
    result = reject_reply(held_reply_id, reason)
    return result


# ─── Pipeline ─────────────────────────────────────────────────────

@api_router.post("/messages/incoming", response_model=PipelineResult)
async def receive_message(incoming: IncomingMessage):
    """Accept an incoming message and run the full pipeline."""
    # Execute the LangGraph Pipeline
    from backend.graph.pipeline_graph import pipeline
    from langchain_core.runnables import RunnableConfig

    # Run the pipeline with the incoming payload
    # Note: pipeline expects a PipelineState mapping
    initial_state = {
        "raw_message": incoming.raw_message,
        "sender_id": incoming.sender_id,
        "sender_name": incoming.sender_name or "Unknown"
    }

    result = pipeline.invoke(initial_state)

    # Extract final output
    return PipelineResult(
        reply_text=result.get("reply_text", "No reply generated."),
        risk_level=result.get("risk_level", "low"),
        requires_approval=result.get("requires_approval", False),
        status="completed",
        trace={"orchestrator_warnings": result.get("orchestrator_warnings", [])}
    )


@api_router.get("/messages/{thread_id}")
async def get_thread_history(thread_id: str):
    """Retrieve message history for a thread."""
    # TODO: Fetch from conversation_threads + messages tables
    return {"thread_id": thread_id, "messages": [], "status": "stub"}


@api_router.get("/dashboard/summary")
async def get_dashboard_summary():
    """Dashboard summary for the owner."""
    # TODO: Aggregate recent results, pending approvals, memory updates
    return {"pending_approvals": 0, "messages_today": 0, "status": "stub"}
