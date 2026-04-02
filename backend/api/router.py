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
import uuid

from backend.config import settings
from backend.models import IncomingMessage, PipelineResult
from backend.services.approval_service import (
    approve_memory,
    reject_memory,
    approve_reply,
    reject_reply,
    record_auto_sent_reply,
    review_reply_record,
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


@api_router.post("/replies/review/{review_record_id}")
def review_reply_record_endpoint(
    review_record_id: str, review_label: str, reviewer_reason: str = ""
):
    return review_reply_record(review_record_id, review_label, reviewer_reason)


# ─── Pipeline ─────────────────────────────────────────────────────


@api_router.post("/messages/incoming", response_model=PipelineResult)
async def receive_message(incoming: IncomingMessage):
    """Accept an incoming message and run the full pipeline."""
    # Execute the LangGraph Pipeline
    from backend.graph.pipeline_graph import pipeline
    from backend.utils.langfuse import get_langfuse_handler
    from backend.db.engine import SessionLocal
    from backend.db.models import Message

    # Run the pipeline with the incoming payload
    # Note: pipeline expects a PipelineState mapping
    initial_state = {
        "raw_message": incoming.raw_message,
        "sender_id": incoming.sender_id,
        "external_sender_id": incoming.sender_id,
        "owner_id": settings.OWNER_ID,
        "trace_id": uuid.uuid4().hex,
        "sender_name": incoming.sender_name or "Unknown",
        "thread_id": incoming.thread_id or incoming.sender_id,
    }

    # Setup Langfuse callbacks if configured
    langfuse_handler = get_langfuse_handler(
        initial_state["trace_id"],
    )
    config = (
        {
            "callbacks": [langfuse_handler],
            "tags": ["api", "langgraph", "orchestrator"],
            "metadata": {
                "langfuse_user_id": incoming.sender_id,
                "langfuse_session_id": initial_state["thread_id"],
                "langfuse_tags": ["api", "langgraph", "orchestrator"],
                "external_id": initial_state["trace_id"],
                "owner_id": settings.OWNER_ID,
                "sender_name": incoming.sender_name or "Unknown",
                "endpoint": "/api/v1/messages/incoming",
            },
        }
        if langfuse_handler
        else {}
    )

    result = pipeline.invoke(initial_state, config=config)

    requires_approval = result.get("requires_approval", False)
    reply_text = result.get("reply_text", "No reply generated.")

    # Only save to thread history if the message is actually delivered to the user
    if not requires_approval and reply_text and reply_text != "No reply generated.":
        session = SessionLocal()
        try:
            message_id = uuid.uuid4()
            outbound_msg = Message(
                id=message_id,
                owner_id=result.get("owner_id", settings.OWNER_ID),
                sender_id=result.get("external_sender_id", incoming.sender_id),
                sender_name=result.get("sender_name", incoming.sender_name or "Unknown"),
                sender_role=result.get("sender_role", "Unknown"),
                direction="outbound",
                content=reply_text,
            )
            session.add(outbound_msg)
            session.commit()
            record_auto_sent_reply(
                owner_id=result.get("owner_id", settings.OWNER_ID),
                trace_id=result.get("trace_id", initial_state["trace_id"]),
                thread_id=result.get("thread_id", initial_state["thread_id"]),
                sender_id=result.get("external_sender_id", incoming.sender_id),
                sender_name=result.get("sender_name", incoming.sender_name or "Unknown"),
                sender_role=result.get("sender_role", "Unknown"),
                raw_message=result.get("raw_message", incoming.raw_message),
                reply_text=reply_text,
                risk_level=result.get("risk_level", "low"),
                risk_flags=result.get("risk_flags", []),
                approval_rule_flags=result.get("approval_rule_flags", []),
                requires_approval=requires_approval,
                message_id=str(message_id),
            )
        except Exception as e:
            print(f"Failed to save outbound message to history: {e}")
        finally:
            session.close()

    # Extract final output
    return PipelineResult(
        reply_text=reply_text,
        risk_level=result.get("risk_level", "low"),
        requires_approval=requires_approval,
        status="completed",
        trace={
            "trace_id": result.get("trace_id", initial_state["trace_id"]),
            "orchestrator_warnings": result.get("orchestrator_warnings", []),
        },
    )


@api_router.get("/replies/review-records")
async def get_reply_review_records(limit: int = 50):
    from backend.db.engine import SessionLocal
    from backend.db.models import ReplyReviewRecord

    session = SessionLocal()
    try:
        rows = (
            session.query(ReplyReviewRecord)
            .order_by(ReplyReviewRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "records": [
                {
                    "id": str(r.id),
                    "trace_id": r.trace_id,
                    "sender_id": r.sender_id,
                    "sender_name": r.sender_name,
                    "sender_role": r.sender_role,
                    "risk_level": r.risk_level,
                    "final_decision": r.final_decision,
                    "review_label": r.review_label,
                    "reviewer_reason": r.reviewer_reason,
                    "held_reply_id": str(r.held_reply_id) if r.held_reply_id else None,
                    "message_id": str(r.message_id) if r.message_id else None,
                    "created_at": str(r.created_at),
                    "reviewed_at": str(r.reviewed_at) if r.reviewed_at else None,
                }
                for r in rows
            ],
            "status": "success",
        }
    finally:
        session.close()


@api_router.get("/messages/{thread_id}")
async def get_thread_history(thread_id: str):
    """Retrieve message history for a thread."""
    from backend.db.engine import SessionLocal
    from backend.db.models import Message

    session = SessionLocal()
    try:
        # thread_id might literally be the sender_id right now
        msgs = (
            session.query(Message)
            .filter((Message.id == thread_id) | (Message.sender_id == thread_id))  # simple fallback
            .order_by(Message.created_at.asc())
            .all()
        )
        return {
            "thread_id": thread_id,
            "messages": [
                {
                    "id": str(m.id),
                    "direction": m.direction,
                    "content": m.content,
                    "created_at": str(m.created_at),
                }
                for m in msgs
            ],
            "status": "success",
        }
    finally:
        session.close()


@api_router.get("/approvals/pending")
async def get_pending_approvals():
    """Fetch all active alerts requiring owner approval."""
    from backend.db.engine import SessionLocal
    from backend.db.models import PendingApproval

    session = SessionLocal()
    try:
        approvals = (
            session.query(PendingApproval)
            .filter(PendingApproval.status == "pending")
            .order_by(PendingApproval.created_at.desc())
            .all()
        )
        return {
            "approvals": [
                {
                    "id": str(a.id),
                    "title": a.title,
                    "sender": a.sender,
                    "preview": a.preview,
                    "proposal_type": a.proposal_type,
                    "risk_level": a.risk_level,
                    "proposal_id": str(a.proposal_id) if a.proposal_id else None,
                    "created_at": str(a.created_at),
                }
                for a in approvals
            ],
            "status": "success",
        }
    finally:
        session.close()


@api_router.get("/dashboard/summary")
async def get_dashboard_summary():
    """Dashboard summary for the owner."""
    from backend.db.engine import SessionLocal
    from backend.db.models import PendingApproval, Message, MemoryUpdateProposal
    from sqlalchemy import func
    from datetime import datetime, date

    session = SessionLocal()
    try:
        # 1. Count pending approvals
        pending_count = (
            session.query(func.count(PendingApproval.id))
            .filter(PendingApproval.status == "pending")
            .scalar()
        )

        # 2. Count messages today
        today = date.today()
        messages_today = (
            session.query(func.count(Message.id))
            .filter(func.date(Message.created_at) == today)
            .scalar()
        )

        # 3. Count total memory updates approved
        memory_updates = (
            session.query(func.count(MemoryUpdateProposal.id))
            .filter(MemoryUpdateProposal.status == "approved")
            .scalar()
        )

        return {
            "pending_approvals": pending_count,
            "messages_today": messages_today,
            "memory_updates_approved": memory_updates,
            "status": "success",
        }
    finally:
        session.close()
