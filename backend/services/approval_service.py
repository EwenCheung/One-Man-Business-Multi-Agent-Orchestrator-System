"""
Owner Approval Service

Handles the hold → notify → approve/reject → send/edit cycle
for replies flagged by the Risk Node and memory updates.
"""

import json
import uuid
from typing import Any, cast
from sqlalchemy import text
from backend.db.engine import SessionLocal


def _format_approved_memory_section(proposed_content: list[dict[str, Any]]) -> str:
    lines = ["## Approved Memory Updates", ""]
    for record in proposed_content:
        memory_type = str(record.get("memory_type") or "memory").strip()
        summary = str(record.get("summary") or record.get("content") or "").strip()
        if not summary:
            continue
        lines.append(f"- ({memory_type}) {summary}")
    return "\n".join(lines).strip()


# ─── Memory Approval ───────────────────────────────────────────────


def approve_memory(proposal_id: str, owner_id: str):
    """Approve a memory update proposal — inserts records into memory_entries."""
    session = SessionLocal()
    try:
        proposal = (
            session.execute(
                text("""
                SELECT *
                FROM public.memory_update_proposals
                WHERE id = :id AND owner_id = :owner_id
            """),
                {"id": proposal_id, "owner_id": owner_id},
            )
            .mappings()
            .first()
        )

        if not proposal:
            raise ValueError("Proposal not found")

        proposed_content = proposal["proposed_content"]
        if isinstance(proposed_content, str):
            proposed_content = json.loads(proposed_content)

        from backend.db.models import MemoryEntry

        entries = []
        for record in proposed_content:
            entries.append(
                MemoryEntry(
                    id=uuid.uuid4(),
                    owner_id=proposal["owner_id"],
                    sender_id=record.get("sender_id"),
                    sender_name=record.get("sender_name"),
                    sender_role=record.get("sender_role"),
                    memory_type=record.get("memory_type"),
                    content=record.get("content"),
                    summary=record.get("summary"),
                    tags=record.get("tags", []),
                    importance=record.get("importance", 0.5),
                )
            )
        if entries:
            session.add_all(entries)

        from backend.db.models import Profile

        try:
            owner_uuid = uuid.UUID(str(proposal["owner_id"]))
        except (ValueError, TypeError):
            owner_uuid = cast(Any, proposal["owner_id"])

        profile = session.query(Profile).filter(Profile.id == owner_uuid).first()
        if profile and proposed_content:
            approved_section = _format_approved_memory_section(proposed_content)
            if approved_section:
                existing_memory = (profile.memory_context or "").strip()
                profile.memory_context = (
                    f"{existing_memory}\n\n{approved_section}".strip()
                    if existing_memory
                    else approved_section
                )

        session.execute(
            text("""
                UPDATE public.memory_update_proposals
                SET status = 'approved',
                    reviewed_at = now()
                WHERE id = :id AND owner_id = :owner_id
            """),
            {"id": proposal_id, "owner_id": owner_id},
        )

        session.execute(
            text("""
                UPDATE public.pending_approvals
                SET status = 'approved'
                WHERE proposal_id = :id AND owner_id = :owner_id
            """),
            {"id": proposal_id, "owner_id": owner_id},
        )

        session.commit()

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reject_memory(proposal_id: str, owner_id: str):
    """Reject a memory update proposal."""
    session = SessionLocal()
    try:
        proposal = (
            session.execute(
                text("""
                SELECT id
                FROM public.memory_update_proposals
                WHERE id = :id AND owner_id = :owner_id
            """),
                {"id": proposal_id, "owner_id": owner_id},
            )
            .mappings()
            .first()
        )

        if not proposal:
            raise ValueError("Proposal not found")

        session.execute(
            text("""
                UPDATE public.memory_update_proposals
                SET status = 'rejected',
                    reviewed_at = now()
                WHERE id = :id AND owner_id = :owner_id
            """),
            {"id": proposal_id, "owner_id": owner_id},
        )

        session.execute(
            text("""
                UPDATE public.pending_approvals
                SET status = 'rejected'
                WHERE proposal_id = :id AND owner_id = :owner_id
            """),
            {"id": proposal_id, "owner_id": owner_id},
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
    risk_flags: list[str],
    approval_rule_flags: list[str] | None = None,
    sender_id: str | None = None,
    sender_name: str | None = None,
    sender_role: str | None = None,
    thread_id: str | None = None,
    trace_id: str | None = None,
    raw_message: str | None = None,
) -> str:
    """
    Save a held reply to the database when risk is MEDIUM or HIGH.
    Also creates a pending_approvals entry for the dashboard.
    Returns the held_reply_id.
    """
    import uuid

    try:
        owner_uuid = uuid.UUID(str(owner_id))
    except (ValueError, TypeError):
        owner_uuid = owner_id

    session = SessionLocal()
    try:
        new_id = uuid.uuid4()
        result = session.execute(
            text("""
                INSERT INTO public.held_replies (
                    id, owner_id, thread_id, sender_id, sender_name,
                    sender_role, reply_text, risk_level, risk_flags, status
                )
                VALUES (
                    :id, :owner_id, :thread_id, :sender_id, :sender_name,
                    :sender_role, :reply_text, :risk_level, CAST(:risk_flags AS jsonb), 'pending'
                )
                RETURNING id
            """),
            {
                "id": new_id,
                "owner_id": owner_uuid,
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
                    id, owner_id, title, sender, preview,
                    proposal_type, risk_level, status, held_reply_id
                )
                VALUES (
                    :id,
                    :owner_id,
                    :title,
                    :sender,
                    :preview,
                    'reply-approval',
                    :risk_level,
                    'pending',
                    :held_reply_id
                )
            """),
            {
                "id": uuid.uuid4(),
                "owner_id": owner_uuid,
                "title": f"Reply requires approval ({risk_level} risk)",
                "sender": sender_name or "Unknown",
                "preview": reply_text[:200],
                "risk_level": risk_level,
                "held_reply_id": new_id,
            },
        )

        session.execute(
            text("""
                INSERT INTO public.reply_review_records (
                    id, owner_id, trace_id, thread_id, sender_id, sender_name, sender_role,
                    raw_message, reply_text, risk_level, risk_flags, approval_rule_flags,
                    requires_approval, final_decision, held_reply_id
                )
                VALUES (
                    :id, :owner_id, :trace_id, :thread_id, :sender_id, :sender_name, :sender_role,
                    :raw_message, :reply_text, :risk_level, CAST(:risk_flags AS jsonb), CAST(:approval_rule_flags AS jsonb),
                    true, 'held_pending_review', :held_reply_id
                )
            """),
            {
                "id": uuid.uuid4(),
                "owner_id": owner_uuid,
                "trace_id": trace_id,
                "thread_id": thread_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "sender_role": sender_role,
                "raw_message": raw_message,
                "reply_text": reply_text,
                "risk_level": risk_level,
                "risk_flags": json.dumps(risk_flags),
                "approval_rule_flags": json.dumps(approval_rule_flags or []),
                "held_reply_id": held_reply_id,
            },
        )

        session.commit()
        return held_reply_id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def approve_reply(held_reply_id: str, owner_id: str) -> dict[str, str]:
    """Approve a held reply — marks as approved and returns the reply text."""
    session = SessionLocal()
    try:
        result = (
            session.execute(
                text("""
                UPDATE public.held_replies
                SET status = 'approved', reviewed_at = now()
                WHERE id = :id AND owner_id = :owner_id
                RETURNING reply_text, owner_id, sender_id, sender_name, sender_role, thread_id
            """),
                {"id": held_reply_id, "owner_id": owner_id},
            )
            .mappings()
            .first()
        )

        if not result:
            raise ValueError("Held reply not found")

        import uuid

        message_id = uuid.uuid4()

        conversation_thread_uuid = None
        if result.get("thread_id"):
            try:
                conversation_thread_uuid = uuid.UUID(str(result["thread_id"]))
            except (ValueError, TypeError):
                conversation_thread_uuid = None

        session.execute(
            text("""
                INSERT INTO public.messages (
                    id, owner_id, conversation_thread_id, sender_id, sender_name, sender_role, direction, content
                )
                VALUES (
                    :id, :owner_id, :conversation_thread_id, :sender_id, :sender_name, :sender_role, 'outbound', :content
                )
            """),
            {
                "id": message_id,
                "owner_id": result["owner_id"],
                "conversation_thread_id": conversation_thread_uuid,
                "sender_id": result["sender_id"],
                "sender_name": result["sender_name"],
                "sender_role": result["sender_role"],
                "content": result["reply_text"],
            },
        )

        if str(result.get("sender_role", "")).lower() != "owner" and conversation_thread_uuid:
            from backend.services.conversation_memory import increment_sender_memory_counter

            _ = increment_sender_memory_counter(
                session,
                owner_id=result["owner_id"],
                conversation_thread_id=conversation_thread_uuid,
                sender_external_id=result["sender_id"],
                sender_name=result["sender_name"],
                sender_role=result["sender_role"],
            )

        session.execute(
            text("""
                UPDATE public.reply_review_records
                SET final_decision = 'approved_and_sent',
                    message_id = :message_id,
                    reviewed_at = now()
                WHERE held_reply_id = :held_reply_id AND owner_id = :owner_id
            """),
            {"held_reply_id": held_reply_id, "message_id": message_id, "owner_id": owner_id},
        )

        session.execute(
            text("""
                UPDATE public.pending_approvals
                SET status = 'approved'
                WHERE held_reply_id = :held_reply_id AND owner_id = :owner_id
            """),
            {"held_reply_id": held_reply_id, "owner_id": owner_id},
        )

        review_record = (
            session.execute(
                text("""
                SELECT raw_message, trace_id
                FROM public.reply_review_records
                WHERE held_reply_id = :held_reply_id AND owner_id = :owner_id
                ORDER BY created_at DESC
                LIMIT 1
            """),
                {"held_reply_id": held_reply_id, "owner_id": owner_id},
            )
            .mappings()
            .first()
        )

        session.commit()

        from backend.integrations.telegram_sender import send_telegram_reply

        _ = send_telegram_reply(
            owner_id=str(result["owner_id"]),
            sender_external_id=result["sender_id"],
            reply_text=result["reply_text"],
        )

        from backend.agents.memory_agent import memory_update_node

        memory_update_node(
            {
                "owner_id": str(result["owner_id"]),
                "external_sender_id": result["sender_id"],
                "sender_name": result["sender_name"],
                "sender_role": result["sender_role"],
                "conversation_thread_id": result.get("thread_id"),
                "thread_id": result.get("thread_id"),
                "trace_id": review_record["trace_id"] if review_record else None,
                "raw_message": review_record["raw_message"] if review_record else "",
                "reply_text": result["reply_text"],
                "completed_tasks": [],
            }
        )

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


def reject_reply(held_reply_id: str, owner_id: str, reason: str = "") -> dict[str, str]:
    """Reject a held reply — marks as rejected."""
    session = SessionLocal()
    try:
        result = (
            session.execute(
                text("""
                UPDATE public.held_replies
                SET status = 'rejected',
                    reviewer_notes = :reason,
                    reviewed_at = now()
                WHERE id = :id AND owner_id = :owner_id
                RETURNING id
            """),
                {"id": held_reply_id, "owner_id": owner_id, "reason": reason},
            )
            .mappings()
            .first()
        )

        if not result:
            raise ValueError("Held reply not found")

        session.execute(
            text("""
                UPDATE public.reply_review_records
                SET final_decision = 'rejected',
                    reviewer_reason = :reason,
                    reviewed_at = now()
                WHERE held_reply_id = :held_reply_id AND owner_id = :owner_id
            """),
            {"held_reply_id": held_reply_id, "reason": reason, "owner_id": owner_id},
        )

        session.execute(
            text("""
                UPDATE public.pending_approvals
                SET status = 'rejected'
                WHERE held_reply_id = :held_reply_id AND owner_id = :owner_id
            """),
            {"held_reply_id": held_reply_id, "owner_id": owner_id},
        )

        session.commit()
        return {"status": "rejected", "held_reply_id": str(result["id"])}

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def review_reply_record(
    review_record_id: str, owner_id: str, review_label: str, reviewer_reason: str = ""
) -> dict[str, str]:
    session = SessionLocal()
    try:
        result = (
            session.execute(
                text("""
                UPDATE public.reply_review_records
                SET review_label = :review_label,
                    reviewer_reason = CASE
                        WHEN :reviewer_reason = '' THEN reviewer_reason
                        ELSE :reviewer_reason
                    END,
                    reviewed_at = now()
                WHERE id = :id AND owner_id = :owner_id
                RETURNING id
            """),
                {
                    "id": review_record_id,
                    "owner_id": owner_id,
                    "review_label": review_label,
                    "reviewer_reason": reviewer_reason,
                },
            )
            .mappings()
            .first()
        )
        if not result:
            raise ValueError("Reply review record not found")
        session.commit()
        return {"status": "reviewed", "reply_review_record_id": str(result["id"])}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def record_auto_sent_reply(
    *,
    owner_id: str,
    trace_id: str | None,
    thread_id: str | None,
    sender_id: str | None,
    sender_name: str | None,
    sender_role: str | None,
    raw_message: str | None,
    reply_text: str,
    risk_level: str,
    risk_flags: list[str],
    approval_rule_flags: list[str] | None,
    requires_approval: bool,
    message_id: str,
) -> None:
    import uuid

    try:
        owner_uuid = uuid.UUID(str(owner_id))
    except (ValueError, TypeError):
        owner_uuid = owner_id
    try:
        message_uuid = uuid.UUID(str(message_id))
    except (ValueError, TypeError):
        message_uuid = message_id

    session = SessionLocal()
    try:
        session.execute(
            text("""
                INSERT INTO public.reply_review_records (
                    id, owner_id, trace_id, thread_id, sender_id, sender_name, sender_role,
                    raw_message, reply_text, risk_level, risk_flags, approval_rule_flags,
                    requires_approval, final_decision, message_id
                )
                VALUES (
                    :id, :owner_id, :trace_id, :thread_id, :sender_id, :sender_name, :sender_role,
                    :raw_message, :reply_text, :risk_level, CAST(:risk_flags AS jsonb), CAST(:approval_rule_flags AS jsonb),
                    :requires_approval, 'auto_sent', :message_id
                )
            """),
            {
                "id": __import__("uuid").uuid4(),
                "owner_id": owner_id,
                "trace_id": trace_id,
                "thread_id": thread_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "sender_role": sender_role,
                "raw_message": raw_message,
                "reply_text": reply_text,
                "risk_level": risk_level,
                "risk_flags": json.dumps(risk_flags),
                "approval_rule_flags": json.dumps(approval_rule_flags or []),
                "requires_approval": requires_approval,
                "message_id": message_id,
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
