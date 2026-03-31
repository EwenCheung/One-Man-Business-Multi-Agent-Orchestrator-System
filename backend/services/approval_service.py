"""
Owner Approval Service

Handles the hold → notify → approve/reject → send/edit cycle
for replies flagged by the Risk Node and memory updates.
"""

import json
from sqlalchemy import text
from backend.db.engine import SessionLocal


# ─── Memory Approval ───────────────────────────────────────────────

def approve_memory(proposal_id: str):
    """Approve a memory update proposal — inserts records into memory_entries."""
    session = SessionLocal()
    try:
        proposal = session.execute(
            text("""
                SELECT *
                FROM public.memory_update_proposals
                WHERE id = :id
            """),
            {"id": proposal_id},
        ).mappings().first()

        if not proposal:
            raise ValueError("Proposal not found")

        proposed_content = proposal["proposed_content"]
        if isinstance(proposed_content, str):
            proposed_content = json.loads(proposed_content)

        for record in proposed_content:
            session.execute(
                text("""
                    INSERT INTO public.memory_entries (
                        owner_id,
                        sender_id,
                        sender_name,
                        sender_role,
                        memory_type,
                        content,
                        summary,
                        tags,
                        importance,
                        created_at
                    )
                    VALUES (
                        :owner_id,
                        :sender_id,
                        :sender_name,
                        :sender_role,
                        :memory_type,
                        :content,
                        :summary,
                        :tags,
                        :importance,
                        now()
                    )
                """),
                {
                    "owner_id": proposal["owner_id"],
                    "sender_id": record.get("sender_id"),
                    "sender_name": record.get("sender_name"),
                    "sender_role": record.get("sender_role"),
                    "memory_type": record.get("memory_type"),
                    "content": record.get("content"),
                    "summary": record.get("summary"),
                    "tags": record.get("tags", []),
                    "importance": record.get("importance", 0.5),
                },
            )

        session.execute(
            text("""
                UPDATE public.memory_update_proposals
                SET status = 'approved',
                    reviewed_at = now()
                WHERE id = :id
            """),
            {"id": proposal_id},
        )

        session.execute(
            text("""
                UPDATE public.pending_approvals
                SET status = 'approved'
                WHERE proposal_id = :id
            """),
            {"id": proposal_id},
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reject_memory(proposal_id: str):
    """Reject a memory update proposal."""
    session = SessionLocal()
    try:
        proposal = session.execute(
            text("""
                SELECT id
                FROM public.memory_update_proposals
                WHERE id = :id
            """),
            {"id": proposal_id},
        ).mappings().first()

        if not proposal:
            raise ValueError("Proposal not found")

        session.execute(
            text("""
                UPDATE public.memory_update_proposals
                SET status = 'rejected',
                    reviewed_at = now()
                WHERE id = :id
            """),
            {"id": proposal_id},
        )

        session.execute(
            text("""
                UPDATE public.pending_approvals
                SET status = 'rejected'
                WHERE proposal_id = :id
            """),
            {"id": proposal_id},
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ─── Reply Approval (Risk Flow) ───────────────────────────────────

def hold_reply(
    owner_id: str,
    reply_text: str,
    risk_level: str,
    risk_flags: list,
    sender_id: str = None,
    sender_name: str = None,
    sender_role: str = None,
    thread_id: str = None,
) -> str:
    """
    Save a held reply to the database when risk is MEDIUM or HIGH.
    Also creates a pending_approvals entry for the dashboard.
    Returns the held_reply_id.
    """
    session = SessionLocal()
    try:
        result = session.execute(
            text("""
                INSERT INTO public.held_replies (
                    owner_id, thread_id, sender_id, sender_name,
                    sender_role, reply_text, risk_level, risk_flags, status
                )
                VALUES (
                    :owner_id, :thread_id, :sender_id, :sender_name,
                    :sender_role, :reply_text, :risk_level, CAST(:risk_flags AS jsonb), 'pending'
                )
                RETURNING id
            """),
            {
                "owner_id": owner_id,
                "thread_id": thread_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "sender_role": sender_role,
                "reply_text": reply_text,
                "risk_level": risk_level,
                "risk_flags": json.dumps(risk_flags),
            },
        )
        held_reply_id = str(result.scalar())

        # Create pending approval entry for dashboard
        session.execute(
            text("""
                INSERT INTO public.pending_approvals (
                    owner_id, title, sender, preview,
                    proposal_type, risk_level, status
                )
                VALUES (
                    :owner_id,
                    :title,
                    :sender,
                    :preview,
                    'reply-approval',
                    :risk_level,
                    'pending'
                )
            """),
            {
                "owner_id": owner_id,
                "title": f"Reply requires approval ({risk_level} risk)",
                "sender": sender_name or "Unknown",
                "preview": reply_text[:200],
                "risk_level": risk_level,
            },
        )

        session.commit()
        return held_reply_id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def approve_reply(held_reply_id: str) -> dict:
    """Approve a held reply — marks as approved and returns the reply text."""
    session = SessionLocal()
    try:
        result = session.execute(
            text("""
                UPDATE public.held_replies
                SET status = 'approved', reviewed_at = now()
                WHERE id = :id
                RETURNING reply_text, owner_id, sender_id, sender_name, sender_role
            """),
            {"id": held_reply_id},
        ).mappings().first()

        if not result:
            raise ValueError("Held reply not found")

        session.commit()
        return {
            "status": "approved",
            "reply_text": result["reply_text"],
            "owner_id": str(result["owner_id"]),
            "sender_id": result["sender_id"],
            "sender_name": result["sender_name"],
            "sender_role": result["sender_role"],
        }

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reject_reply(held_reply_id: str, reason: str = "") -> dict:
    """Reject a held reply — marks as rejected."""
    session = SessionLocal()
    try:
        result = session.execute(
            text("""
                UPDATE public.held_replies
                SET status = 'rejected',
                    reviewer_notes = :reason,
                    reviewed_at = now()
                WHERE id = :id
                RETURNING id
            """),
            {"id": held_reply_id, "reason": reason},
        ).mappings().first()

        if not result:
            raise ValueError("Held reply not found")

        session.commit()
        return {"status": "rejected", "held_reply_id": str(result["id"])}

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()