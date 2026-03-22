"""
API Router — REST endpoints for the orchestrator.

Endpoints:
  POST  /api/v1/messages/incoming       → run the pipeline
  GET   /api/v1/messages/{thread_id}    → thread history (stub)
  POST  /api/v1/messages/{id}/approve   → approve held reply (stub)
  GET   /api/v1/dashboard/summary       → dashboard data (stub)
"""

from fastapi import APIRouter

from backend.models import IncomingMessage, PipelineResult

api_router = APIRouter(tags=["orchestrator"])


@api_router.post("/messages/incoming", response_model=PipelineResult)
async def receive_message(incoming: IncomingMessage):
    """Accept an incoming message and run the full pipeline."""
    # TODO: Call pipeline graph
    # from backend.graph.pipeline_graph import pipeline
    # result = pipeline.invoke({
    #     "raw_message": incoming.raw_message,
    #     "sender_id": incoming.sender_id,
    #     #...
    # })
    return PipelineResult(status="stub — pipeline not yet wired")


@api_router.get("/messages/{thread_id}")
async def get_thread_history(thread_id: str):
    """Retrieve message history for a thread."""
    # TODO: Fetch from conversation_threads + messages tables
    return {"thread_id": thread_id, "messages": [], "status": "stub"}


@api_router.post("/messages/{message_id}/approve")
async def approve_message(message_id: str):
    """Owner approves a held reply."""
    # TODO: Update message status, trigger send + update agent
    return {"message_id": message_id, "approved": True, "status": "stub"}


@api_router.get("/dashboard/summary")
async def get_dashboard_summary():
    """Dashboard summary for the owner."""
    # TODO: Aggregate recent results, pending approvals, memory updates
    return {"pending_approvals": 0, "messages_today": 0, "status": "stub"}
