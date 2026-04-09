from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.db.models import (
    ConversationMemory,
    ConversationSenderMemory,
    ConversationThread,
    EntityMemory,
    HeldReply,
    Message,
    OwnerMemoryRule,
    PendingApproval,
    Profile,
    ReplyReviewRecord,
)


def _coerce_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_conversation_thread(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    sender_role: str,
    external_sender_id: str,
    sender_name: str | None,
    sender_channel: str = "api",
    requested_thread_id: str | None = None,
) -> ConversationThread:
    owner_uuid = _coerce_uuid(owner_id)
    if owner_uuid is None:
        raise ValueError("owner_id must be a valid UUID")

    sender_role_norm = (sender_role or "").strip().lower()
    now = _utc_now()

    if sender_role_norm == "owner":
        existing_owner_thread: ConversationThread | None = None
        requested_uuid = _coerce_uuid(requested_thread_id)
        if requested_uuid is not None:
            existing_owner_thread = (
                session.query(ConversationThread)
                .filter(
                    ConversationThread.id == requested_uuid,
                    ConversationThread.owner_id == owner_uuid,
                    ConversationThread.thread_type == "owner_chat",
                )
                .first()
            )

        if existing_owner_thread is None:
            existing_owner_thread = (
                session.query(ConversationThread)
                .filter(
                    ConversationThread.owner_id == owner_uuid,
                    ConversationThread.thread_type == "owner_chat",
                )
                .order_by(ConversationThread.updated_at.desc())
                .first()
            )

        if existing_owner_thread is None:
            existing_owner_thread = ConversationThread(
                owner_id=owner_uuid,
                thread_type="owner_chat",
                title="Owner Chat",
                sender_name=sender_name or "Owner",
                sender_role="owner",
                sender_channel=sender_channel,
                last_message_at=now,
                updated_at=now,
            )
            session.add(existing_owner_thread)
            session.flush()
        else:
            existing_owner_thread.last_message_at = now
            existing_owner_thread.updated_at = now

        return existing_owner_thread

    thread = (
        session.query(ConversationThread)
        .filter(
            ConversationThread.owner_id == owner_uuid,
            ConversationThread.thread_type == "external_sender",
            ConversationThread.sender_channel == sender_channel,
            ConversationThread.sender_external_id == external_sender_id,
        )
        .first()
    )

    if thread is None:
        thread = ConversationThread(
            owner_id=owner_uuid,
            thread_type="external_sender",
            title=(sender_name or external_sender_id or "External Sender").strip()[:120],
            sender_external_id=external_sender_id,
            sender_name=sender_name,
            sender_role=sender_role_norm or "customer",
            sender_channel=sender_channel,
            last_message_at=now,
            updated_at=now,
        )
        session.add(thread)
        session.flush()
    else:
        thread.sender_name = sender_name or thread.sender_name
        thread.sender_role = sender_role_norm or thread.sender_role
        thread.last_message_at = now
        thread.updated_at = now

    return thread


def add_message_to_thread(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    conversation_thread_id: str | uuid.UUID,
    sender_id: str | None,
    sender_name: str | None,
    sender_role: str | None,
    direction: str,
    content: str,
) -> Message:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(conversation_thread_id)
    if owner_uuid is None or thread_uuid is None:
        raise ValueError("owner_id and conversation_thread_id must be valid UUIDs")

    message = Message(
        id=uuid.uuid4(),
        owner_id=owner_uuid,
        conversation_thread_id=thread_uuid,
        sender_id=sender_id,
        sender_name=sender_name,
        sender_role=sender_role,
        direction=direction,
        content=content,
    )
    session.add(message)
    return message


def get_short_term_memory(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    conversation_thread_id: str | uuid.UUID,
    limit: int = 10,
) -> list[dict[str, str]]:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(conversation_thread_id)
    if owner_uuid is None or thread_uuid is None:
        return []

    rows = (
        session.query(Message)
        .filter(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == thread_uuid,
        )
        .order_by(Message.created_at.desc())
        .limit(max(1, limit))
        .all()
    )

    out: list[dict[str, str]] = []
    for msg in reversed(rows):
        role = "user" if (msg.direction or "").lower() == "inbound" else "assistant"
        out.append({"role": role, "content": msg.content})
    return out


def get_long_term_owner_memory(session: Session, *, owner_id: str | uuid.UUID) -> str:
    owner_uuid = _coerce_uuid(owner_id)
    if owner_uuid is None:
        return "No long-term owner memory available."

    profile = session.query(Profile).filter(Profile.id == owner_uuid).first()
    profile_memory_context = ((profile.memory_context or "") if profile else "").strip()

    owner_rules = (
        session.query(OwnerMemoryRule)
        .filter(OwnerMemoryRule.owner_id == owner_uuid)
        .order_by(OwnerMemoryRule.updated_at.desc())
        .limit(40)
        .all()
    )

    durable_owner_memories = (
        session.query(EntityMemory)
        .filter(
            EntityMemory.owner_id == owner_uuid,
            EntityMemory.entity_role == "owner",
        )
        .order_by(EntityMemory.updated_at.desc())
        .limit(40)
        .all()
    )

    sections: list[str] = []
    if profile_memory_context:
        sections.append("Owner Memory Context:\n" + profile_memory_context)
    if owner_rules:
        sections.append(
            "Owner Rules:\n" + "\n".join(f"- [{r.category}] {r.content}" for r in owner_rules)
        )
    if durable_owner_memories:
        sections.append(
            "Durable Owner Business Memory:\n"
            + "\n".join(
                f"- ({m.memory_type}) {m.summary or m.content}" for m in durable_owner_memories
            )
        )

    return "\n\n".join(sections) if sections else "No long-term owner memory available."


def get_profile_contexts(session: Session, *, owner_id: str | uuid.UUID) -> dict[str, str]:
    owner_uuid = _coerce_uuid(owner_id)
    if owner_uuid is None:
        return {
            "memory_context": "",
            "soul_context": "",
            "rule_context": "",
            "business_description": "",
        }

    profile = session.query(Profile).filter(Profile.id == owner_uuid).first()
    if profile is None:
        return {
            "memory_context": "",
            "soul_context": "",
            "rule_context": "",
            "business_description": "",
        }

    return {
        "memory_context": (profile.memory_context or "").strip(),
        "soul_context": (profile.soul_context or "").strip(),
        "rule_context": (profile.rule_context or "").strip(),
        "business_description": (profile.business_description or "").strip(),
    }


def get_sender_memory_summary(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    conversation_thread_id: str | uuid.UUID,
    sender_external_id: str,
) -> str:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(conversation_thread_id)
    if owner_uuid is None or thread_uuid is None:
        return "No sender memory summary available yet."

    row = (
        session.query(ConversationSenderMemory)
        .filter(
            ConversationSenderMemory.owner_id == owner_uuid,
            ConversationSenderMemory.conversation_thread_id == thread_uuid,
            ConversationSenderMemory.sender_external_id == sender_external_id,
        )
        .first()
    )
    if not row or not (row.summary or "").strip():
        return "No sender memory summary available yet."
    return row.summary


def increment_sender_memory_counter(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    conversation_thread_id: str | uuid.UUID,
    sender_external_id: str,
    sender_name: str | None,
    sender_role: str | None,
) -> ConversationSenderMemory | None:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(conversation_thread_id)
    if owner_uuid is None or thread_uuid is None:
        return None

    now = _utc_now()
    row = (
        session.query(ConversationSenderMemory)
        .filter(
            ConversationSenderMemory.owner_id == owner_uuid,
            ConversationSenderMemory.conversation_thread_id == thread_uuid,
            ConversationSenderMemory.sender_external_id == sender_external_id,
        )
        .first()
    )

    if row is None:
        row = ConversationSenderMemory(
            owner_id=owner_uuid,
            conversation_thread_id=thread_uuid,
            sender_external_id=sender_external_id,
            sender_name=sender_name,
            sender_role=sender_role,
            summary="No sender memory summary available yet.",
            message_count_since_update=1,
            last_message_at=now,
        )
        session.add(row)
        session.flush()
        return row

    row.sender_name = sender_name or row.sender_name
    row.sender_role = sender_role or row.sender_role
    row.last_message_at = now
    row.message_count_since_update = int(row.message_count_since_update or 0) + 1
    row.updated_at = now
    session.flush()
    return row


def get_sender_summary_threshold(session: Session, *, owner_id: str | uuid.UUID) -> int:
    owner_uuid = _coerce_uuid(owner_id)
    if owner_uuid is None:
        return 20

    profile = session.query(Profile).filter(Profile.id == owner_uuid).first()
    threshold = (
        int(profile.sender_summary_threshold)
        if profile and profile.sender_summary_threshold
        else 20
    )
    return threshold if threshold > 0 else 20


def get_recent_thread_messages(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    conversation_thread_id: str | uuid.UUID,
    limit: int = 24,
) -> list[Message]:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(conversation_thread_id)
    if owner_uuid is None or thread_uuid is None:
        return []

    rows = (
        session.query(Message)
        .filter(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == thread_uuid,
        )
        .order_by(Message.created_at.desc())
        .limit(max(1, limit))
        .all()
    )
    return list(reversed(rows))


def build_three_layer_memory_context(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    conversation_thread_id: str | uuid.UUID,
    sender_external_id: str,
) -> dict[str, str | list[dict[str, str]]]:
    return {
        "long_term_memory": get_long_term_owner_memory(session, owner_id=owner_id),
        "sender_memory": get_sender_memory_summary(
            session,
            owner_id=owner_id,
            conversation_thread_id=conversation_thread_id,
            sender_external_id=sender_external_id,
        ),
        "short_term_memory": get_short_term_memory(
            session,
            owner_id=owner_id,
            conversation_thread_id=conversation_thread_id,
            limit=10,
        ),
    }


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _normalize_sender_roles(sender_roles: str | None) -> list[str]:
    if not sender_roles:
        return []
    return [r.strip().lower() for r in sender_roles.split(",") if r.strip()]


def list_external_sender_threads(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    sender_roles: str | None = None,
    limit: int = 100,
) -> dict[str, object]:
    owner_uuid = _coerce_uuid(owner_id)
    if owner_uuid is None:
        raise ValueError("owner_id must be a valid UUID")

    message_count_subquery = (
        select(func.count(Message.id))
        .where(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == ConversationThread.id,
        )
        .correlate(ConversationThread)
        .scalar_subquery()
    )
    latest_content_subquery = (
        select(Message.content)
        .where(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == ConversationThread.id,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(ConversationThread)
        .scalar_subquery()
    )
    latest_direction_subquery = (
        select(Message.direction)
        .where(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == ConversationThread.id,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(ConversationThread)
        .scalar_subquery()
    )
    latest_message_at_subquery = (
        select(Message.created_at)
        .where(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == ConversationThread.id,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(ConversationThread)
        .scalar_subquery()
    )

    query = (
        session.query(
            ConversationThread,
            ConversationSenderMemory.summary.label("sender_summary"),
            ConversationSenderMemory.message_count_since_update.label("summary_pending_count"),
            ConversationSenderMemory.last_summarized_at.label("last_summarized_at"),
            latest_content_subquery.label("latest_preview"),
            latest_direction_subquery.label("latest_direction"),
            latest_message_at_subquery.label("latest_message_at_from_messages"),
            message_count_subquery.label("message_count"),
        )
        .outerjoin(
            ConversationSenderMemory,
            and_(
                ConversationSenderMemory.owner_id == ConversationThread.owner_id,
                ConversationSenderMemory.conversation_thread_id == ConversationThread.id,
                ConversationSenderMemory.sender_external_id
                == ConversationThread.sender_external_id,
            ),
        )
        .filter(
            ConversationThread.owner_id == owner_uuid,
            ConversationThread.thread_type == "external_sender",
        )
    )

    normalized_roles = _normalize_sender_roles(sender_roles)
    if normalized_roles:
        query = query.filter(func.lower(ConversationThread.sender_role).in_(normalized_roles))

    rows = (
        query.order_by(
            ConversationThread.last_message_at.desc(),
            ConversationThread.updated_at.desc(),
        )
        .limit(max(1, limit))
        .all()
    )

    items: list[dict[str, object]] = []
    for row in rows:
        thread: ConversationThread = row.ConversationThread
        latest_at = row.latest_message_at_from_messages or thread.last_message_at
        items.append(
            {
                "thread_id": str(thread.id),
                "thread_type": thread.thread_type,
                "sender": {
                    "external_id": thread.sender_external_id,
                    "name": thread.sender_name,
                    "role": thread.sender_role,
                    "channel": thread.sender_channel,
                },
                "title": thread.title,
                "preview": row.latest_preview,
                "latest_direction": row.latest_direction,
                "last_message_at": _to_iso(latest_at),
                "message_count": int(row.message_count or 0),
                "unread_count": None,
                "unread_tracking": "not_supported",
                "pending_summary_count": int(row.summary_pending_count or 0),
                "sender_summary_available": bool((row.sender_summary or "").strip()),
                "last_summarized_at": _to_iso(row.last_summarized_at),
                "updated_at": _to_iso(thread.updated_at),
            }
        )

    return {
        "threads": items,
        "filters": {
            "sender_roles": normalized_roles,
        },
        "status": "success",
    }


def get_external_sender_thread_detail(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    thread_id: str,
) -> dict[str, object] | None:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(thread_id)
    if owner_uuid is None or thread_uuid is None:
        return None

    thread = (
        session.query(ConversationThread)
        .filter(
            ConversationThread.id == thread_uuid,
            ConversationThread.owner_id == owner_uuid,
            ConversationThread.thread_type == "external_sender",
        )
        .first()
    )
    if thread is None:
        return None

    sender_memory = (
        session.query(ConversationSenderMemory)
        .filter(
            ConversationSenderMemory.owner_id == owner_uuid,
            ConversationSenderMemory.conversation_thread_id == thread_uuid,
            ConversationSenderMemory.sender_external_id == thread.sender_external_id,
        )
        .first()
    )

    messages = (
        session.query(Message)
        .filter(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == thread_uuid,
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    return {
        "thread": {
            "thread_id": str(thread.id),
            "thread_type": thread.thread_type,
            "title": thread.title,
            "last_message_at": _to_iso(thread.last_message_at),
            "sender": {
                "external_id": thread.sender_external_id,
                "name": thread.sender_name,
                "role": thread.sender_role,
                "channel": thread.sender_channel,
            },
        },
        "sender_summary": {
            "summary": sender_memory.summary if sender_memory else None,
            "pending_summary_count": int(sender_memory.message_count_since_update or 0)
            if sender_memory
            else 0,
            "last_message_at": _to_iso(sender_memory.last_message_at) if sender_memory else None,
            "last_summarized_at": _to_iso(sender_memory.last_summarized_at)
            if sender_memory
            else None,
        },
        "messages": [
            {
                "id": str(message.id),
                "direction": message.direction,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": message.sender_name,
                "sender_role": message.sender_role,
                "created_at": _to_iso(message.created_at),
            }
            for message in messages
        ],
        "status": "success",
    }


def list_owner_chat_threads(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    limit: int = 100,
) -> dict[str, object]:
    owner_uuid = _coerce_uuid(owner_id)
    if owner_uuid is None:
        raise ValueError("owner_id must be a valid UUID")

    message_count_subquery = (
        select(func.count(Message.id))
        .where(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == ConversationThread.id,
        )
        .correlate(ConversationThread)
        .scalar_subquery()
    )
    latest_content_subquery = (
        select(Message.content)
        .where(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == ConversationThread.id,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(ConversationThread)
        .scalar_subquery()
    )
    latest_message_at_subquery = (
        select(Message.created_at)
        .where(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == ConversationThread.id,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
        .correlate(ConversationThread)
        .scalar_subquery()
    )

    rows = (
        session.query(
            ConversationThread,
            latest_content_subquery.label("latest_preview"),
            latest_message_at_subquery.label("latest_message_at_from_messages"),
            message_count_subquery.label("message_count"),
        )
        .filter(
            ConversationThread.owner_id == owner_uuid,
            ConversationThread.thread_type == "owner_chat",
        )
        .order_by(ConversationThread.last_message_at.desc(), ConversationThread.updated_at.desc())
        .limit(max(1, limit))
        .all()
    )

    return {
        "threads": [
            {
                "thread_id": str(row.ConversationThread.id),
                "thread_type": row.ConversationThread.thread_type,
                "title": row.ConversationThread.title,
                "preview": row.latest_preview,
                "last_message_at": _to_iso(
                    row.latest_message_at_from_messages or row.ConversationThread.last_message_at
                ),
                "message_count": int(row.message_count or 0),
                "updated_at": _to_iso(row.ConversationThread.updated_at),
            }
            for row in rows
        ],
        "status": "success",
    }


def get_owner_chat_thread_detail(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    thread_id: str,
) -> dict[str, object] | None:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(thread_id)
    if owner_uuid is None or thread_uuid is None:
        return None

    thread = (
        session.query(ConversationThread)
        .filter(
            ConversationThread.id == thread_uuid,
            ConversationThread.owner_id == owner_uuid,
            ConversationThread.thread_type == "owner_chat",
        )
        .first()
    )
    if thread is None:
        return None

    messages = (
        session.query(Message)
        .filter(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == thread_uuid,
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    return {
        "thread": {
            "thread_id": str(thread.id),
            "thread_type": thread.thread_type,
            "title": thread.title,
            "last_message_at": _to_iso(thread.last_message_at),
            "sender": {
                "external_id": thread.sender_external_id,
                "name": thread.sender_name,
                "role": thread.sender_role,
                "channel": thread.sender_channel,
            },
        },
        "messages": [
            {
                "id": str(message.id),
                "direction": message.direction,
                "content": message.content,
                "sender_id": message.sender_id,
                "sender_name": message.sender_name,
                "sender_role": message.sender_role,
                "created_at": _to_iso(message.created_at),
            }
            for message in messages
        ],
        "status": "success",
    }


def delete_owner_chat_thread(
    session: Session,
    *,
    owner_id: str | uuid.UUID,
    thread_id: str,
) -> dict[str, object] | None:
    owner_uuid = _coerce_uuid(owner_id)
    thread_uuid = _coerce_uuid(thread_id)
    if owner_uuid is None or thread_uuid is None:
        return None

    thread = (
        session.query(ConversationThread)
        .filter(
            ConversationThread.id == thread_uuid,
            ConversationThread.owner_id == owner_uuid,
            ConversationThread.thread_type == "owner_chat",
        )
        .first()
    )
    if thread is None:
        return None

    message_ids = [
        row[0]
        for row in session.query(Message.id)
        .filter(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == thread_uuid,
        )
        .all()
    ]

    held_reply_ids = [
        row[0]
        for row in session.query(HeldReply.id)
        .filter(
            HeldReply.owner_id == owner_uuid,
            HeldReply.thread_id == str(thread_uuid),
        )
        .all()
    ]

    if held_reply_ids:
        _ = (
            session.query(PendingApproval)
            .filter(
                PendingApproval.owner_id == owner_uuid,
                PendingApproval.held_reply_id.in_(held_reply_ids),
            )
            .delete(synchronize_session=False)
        )

    if message_ids:
        _ = (
            session.query(ReplyReviewRecord)
            .filter(
                ReplyReviewRecord.owner_id == owner_uuid,
                ReplyReviewRecord.message_id.in_(message_ids),
            )
            .delete(synchronize_session=False)
        )

    if held_reply_ids:
        _ = (
            session.query(ReplyReviewRecord)
            .filter(
                ReplyReviewRecord.owner_id == owner_uuid,
                ReplyReviewRecord.held_reply_id.in_(held_reply_ids),
            )
            .delete(synchronize_session=False)
        )
        _ = (
            session.query(HeldReply)
            .filter(
                HeldReply.owner_id == owner_uuid,
                HeldReply.id.in_(held_reply_ids),
            )
            .delete(synchronize_session=False)
        )

    deleted_messages = (
        session.query(Message)
        .filter(
            Message.owner_id == owner_uuid,
            Message.conversation_thread_id == thread_uuid,
        )
        .delete(synchronize_session=False)
    )
    _ = (
        session.query(ConversationSenderMemory)
        .filter(
            ConversationSenderMemory.owner_id == owner_uuid,
            ConversationSenderMemory.conversation_thread_id == thread_uuid,
        )
        .delete(synchronize_session=False)
    )
    _ = (
        session.query(ConversationMemory)
        .filter(
            ConversationMemory.owner_id == owner_uuid,
            ConversationMemory.conversation_thread_id == thread_uuid,
        )
        .delete(synchronize_session=False)
    )
    session.delete(thread)

    return {
        "thread_id": str(thread_uuid),
        "deleted_messages": int(deleted_messages or 0),
        "status": "success",
    }
