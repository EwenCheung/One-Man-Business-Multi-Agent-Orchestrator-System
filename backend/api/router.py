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
    from backend.utils.langfuse import get_langfuse_handler
    from backend.db.engine import SessionLocal
    from backend.db.models import Message, Customer, Supplier, Partner, Investor

    # Run the pipeline with the incoming payload
    # Note: pipeline expects a PipelineState mapping
    initial_state = {
        "raw_message": incoming.raw_message,
        "sender_id": incoming.sender_id,
        "sender_name": incoming.sender_name or "Unknown",
        "thread_id": incoming.thread_id or incoming.sender_id
    }

    # Setup Langfuse callbacks if configured
    langfuse_handler = get_langfuse_handler()
    config = {"callbacks": [langfuse_handler]} if langfuse_handler else {}

    result = pipeline.invoke(initial_state, config=config)

    requires_approval = result.get("requires_approval", False)
    reply_text = result.get("reply_text", "No reply generated.")
    
    # Only save to thread history if the message is actually delivered to the user
    if not requires_approval and reply_text and reply_text != "No reply generated.":
        session = SessionLocal()
        try:
            owner_id_to_use = "00000000-0000-0000-0000-000000000000"
            sender_id = incoming.sender_id
            
            c = session.query(Customer).filter_by(id=sender_id).first()
            if c: owner_id_to_use = c.owner_id
            else:
                s = session.query(Supplier).filter_by(id=sender_id).first()
                if s: owner_id_to_use = s.owner_id
                else:
                    p = session.query(Partner).filter_by(id=sender_id).first()
                    if p: owner_id_to_use = p.owner_id
                    else:
                        i = session.query(Investor).filter_by(id=sender_id).first()
                        if i: owner_id_to_use = i.owner_id

            outbound_msg = Message(
                owner_id=owner_id_to_use,
                sender_id=sender_id,
                sender_role=result.get("sender_role", "Unknown"),
                direction="outbound",
                content=reply_text
            )
            session.add(outbound_msg)
            session.commit()
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
        trace={"orchestrator_warnings": result.get("orchestrator_warnings", [])}
    )


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
            .filter((Message.id == thread_id) | (Message.sender_id == thread_id)) # simple fallback
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
                    "created_at": str(m.created_at)
                } for m in msgs
            ],
            "status": "success"
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
                    "created_at": str(a.created_at)
                } for a in approvals
            ],
            "status": "success"
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
        pending_count = session.query(func.count(PendingApproval.id)).filter(
            PendingApproval.status == "pending"
        ).scalar()
        
        # 2. Count messages today
        today = date.today()
        messages_today = session.query(func.count(Message.id)).filter(
            func.date(Message.created_at) == today
        ).scalar()
        
        # 3. Count total memory updates approved
        memory_updates = session.query(func.count(MemoryUpdateProposal.id)).filter(
            MemoryUpdateProposal.status == "approved"
        ).scalar()

        return {
            "pending_approvals": pending_count,
            "messages_today": messages_today,
            "memory_updates_approved": memory_updates,
            "status": "success"
        }
    finally:
        session.close()
