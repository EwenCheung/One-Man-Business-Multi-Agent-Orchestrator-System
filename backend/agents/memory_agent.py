from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from collections.abc import Mapping
from typing import Any, Literal, cast

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db.engine import SessionLocal
from backend.graph.state import SubTask
from backend.models.agent_response import AgentResponse
from backend.services.conversation_memory import (
    get_recent_thread_messages,
    get_sender_summary_threshold,
)
from backend.utils.llm_provider import get_chat_llm

logger = logging.getLogger(__name__)

MEMORY_READ_PROMPT = """\
You are a Deep Memory Retrieval Agent.

Your job is to read retrieved historical records and summarize only the memory
that is relevant to the query.

Instructions:
- Use ONLY the provided records.
- Do NOT invent facts.
- Return concise summaries, not raw logs.
- Classify each memory item as one of:
  - recent   -> important and from the last 7 days
  - durable  -> long-term relevant fact, preference, decision, or constraint
  - stale    -> older and potentially outdated, so should be treated cautiously
- If nothing relevant exists, return empty lists.

User Query:
{task_description}

Retrieved Records:
{retrieved_records}
"""

MEMORY_UPDATE_PROMPT = """\
You are a Memory Update Agent.

Your job is to extract durable business memory from a completed interaction.

Extract ONLY high-value memory:
- preferences
- constraints
- unresolved follow-ups
- decisions / commitments
- relationship signals

Do NOT include:
- greetings
- filler
- repeated obvious facts
- transient noise

Return structured output.

Sender:
- name: {sender_name}
- role: {sender_role}
- id: {sender_id}

Original Message:
{raw_message}

Reply Sent:
{reply_text}

Completed Tasks Summary:
{completed_tasks_summary}
"""


OWNER_MEMORY_UPDATE_PROMPT = """\
You are an expert Executive Assistant. Your job is to update the long-term memory document for the business owner.
You must compact the new interactions into the existing memory context, keeping the total document under 200 lines.

Business Description:
{business_description}

Existing Memory Context:
{previous_memory}

New Interaction to Integrate:
Owner said: {raw_message}
System did/replied: {reply_text}
Completed Tasks: {completed_tasks_summary}

Please output the updated, fully compacted memory context in plain text format. Retain all important historical facts, but integrate the new information logically and concisely.
"""

SENDER_SUMMARY_PROMPT = """\
You maintain sender memory for an external conversation thread.

Summarize this sender in a compact profile for future replies.

Include:
- who this person is in relation to the business
- stable preferences and communication style
- personality / negotiation style signals
- recurring topics and unresolved asks

Do not include transient one-off details unless they indicate durable patterns.
Return plain text only.

Previous Summary:
{previous_summary}

Recent Thread Messages (chronological):
{messages}
"""


# ────────────────────────────────────────────────────────
# STRUCTURED OUTPUT SCHEMAS
# ────────────────────────────────────────────────────────


class MemoryReadItem(BaseModel):
    summary: str = Field(description="Concise factual summary")
    source: str = Field(description="messages | memory_entries")
    created_at: str | None = Field(default=None)
    confidence: float = Field(default=0.5)


class MemoryReadSummary(BaseModel):
    recent: list[MemoryReadItem] = Field(default_factory=list)
    durable: list[MemoryReadItem] = Field(default_factory=list)
    stale: list[MemoryReadItem] = Field(default_factory=list)


class MemoryUpdateExtraction(BaseModel):
    preferences: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    relationship: list[str] = Field(default_factory=list)


RiskLevel = Literal["low", "medium", "high"]


# ────────────────────────────────────────────────────────
# GENERIC HELPERS
# ────────────────────────────────────────────────────────


def _get_llm(scope: str = "memory"):
    return get_chat_llm(scope=scope, temperature=0.0)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, indent=2)


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return {}


def _get_owner_id_from_state(state: Mapping[str, object]) -> str | None:
    if state.get("owner_id"):
        return str(state["owner_id"])

    injected = _as_mapping(state.get("injected_context", {}))
    if injected.get("owner_id"):
        return str(injected["owner_id"])

    return None


def _get_sender_id_from_state(state: Mapping[str, object]) -> str | None:
    if state.get("external_sender_id"):
        return str(state["external_sender_id"])

    if state.get("sender_id"):
        return str(state["sender_id"])

    injected = _as_mapping(state.get("injected_context", {}))
    if injected.get("external_sender_id"):
        return str(injected["external_sender_id"])

    if injected.get("sender_id"):
        return str(injected["sender_id"])

    return None


def _get_sender_role_from_state(state: Mapping[str, object]) -> str | None:
    if state.get("sender_role"):
        return str(state["sender_role"])

    injected = _as_mapping(state.get("injected_context", {}))
    if injected.get("sender_role"):
        return str(injected["sender_role"])

    return None


def _get_sender_name_from_state(state: Mapping[str, object]) -> str | None:
    if state.get("sender_name"):
        return str(state["sender_name"])

    injected = _as_mapping(state.get("injected_context", {}))
    if injected.get("sender_name"):
        return str(injected["sender_name"])

    return None


def _get_conversation_thread_id_from_state(state: Mapping[str, object]) -> str | None:
    if state.get("conversation_thread_id"):
        return str(state["conversation_thread_id"])

    if state.get("thread_id"):
        candidate = str(state["thread_id"])
        try:
            uuid.UUID(candidate)
            return candidate
        except (ValueError, TypeError):
            pass

    injected = _as_mapping(state.get("injected_context", {}))
    if injected.get("conversation_thread_id"):
        return str(injected["conversation_thread_id"])

    if injected.get("thread_id"):
        candidate = str(injected["thread_id"])
        try:
            uuid.UUID(candidate)
            return candidate
        except (ValueError, TypeError):
            pass

    return None


def _safe_completed_tasks_summary(state: Mapping[str, object]) -> str:
    completed_tasks_raw = state.get("completed_tasks", [])
    completed_tasks = completed_tasks_raw if isinstance(completed_tasks_raw, list) else []
    if not completed_tasks:
        return ""

    parts: list[str] = []
    for task in completed_tasks:
        if not isinstance(task, Mapping):
            continue
        task_map = cast(Mapping[str, object], task)
        task_id = task_map.get("task_id", "?")
        assignee = task_map.get("assignee", "?")
        result = _normalize_text(task_map.get("result", ""))
        parts.append(f"Task {task_id} ({assignee}): {result}")
    return "\n".join(parts)


# ────────────────────────────────────────────────────────
# DB ACCESS — READ MODE
# ────────────────────────────────────────────────────────


def _search_messages(
    session: Session,
    owner_id: str,
    query: str,
    sender_id: str | None = None,
    sender_role: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT id, sender_id, sender_name, sender_role, direction, content, created_at
        FROM public.messages
        WHERE owner_id = :owner_id
          AND content ILIKE :query
    """
    params: dict[str, Any] = {
        "owner_id": owner_id,
        "query": f"%{query}%",
    }

    normalized_role = (sender_role or "").strip().lower()
    if normalized_role == "owner":
        pass
    elif sender_id:
        sql += " AND sender_id = :sender_id"
        params["sender_id"] = sender_id
    else:
        return []

    sql += " ORDER BY created_at DESC LIMIT 8"

    rows = session.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _search_memory_entries(
    session: Session,
    owner_id: str,
    query: str,
    sender_id: str | None = None,
    sender_role: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT id, sender_id, sender_name, sender_role, memory_type, content, summary, tags, importance, created_at
        FROM public.memory_entries
        WHERE owner_id = :owner_id
          AND (
                content ILIKE :query
                OR summary ILIKE :query
              )
    """
    params: dict[str, Any] = {
        "owner_id": owner_id,
        "query": f"%{query}%",
    }

    normalized_role = (sender_role or "").strip().lower()
    if normalized_role == "owner":
        pass
    elif sender_id:
        sql += " AND sender_id = :sender_id"
        params["sender_id"] = sender_id
    else:
        return []

    sql += " ORDER BY created_at DESC LIMIT 8"

    rows = session.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _format_retrieved_records(
    messages: list[dict[str, Any]], memories: list[dict[str, Any]]
) -> str:
    payload = {
        "messages": [
            {
                "source": "messages",
                "id": row.get("id"),
                "sender_id": row.get("sender_id"),
                "sender_name": row.get("sender_name"),
                "sender_role": row.get("sender_role"),
                "direction": row.get("direction"),
                "content": row.get("content"),
                "created_at": row.get("created_at"),
            }
            for row in messages
        ],
        "memory_entries": [
            {
                "source": "memory_entries",
                "id": row.get("id"),
                "sender_id": row.get("sender_id"),
                "sender_name": row.get("sender_name"),
                "sender_role": row.get("sender_role"),
                "memory_type": row.get("memory_type"),
                "summary": row.get("summary"),
                "content": row.get("content"),
                "tags": row.get("tags"),
                "importance": row.get("importance"),
                "created_at": row.get("created_at"),
            }
            for row in memories
        ],
    }
    return _json_dump(payload)


# ────────────────────────────────────────────────────────
# DB ACCESS — UPDATE MODE
# ────────────────────────────────────────────────────────


def _insert_memory_entries(session: Session, records: list[dict[str, Any]]) -> None:
    import uuid
    from backend.db.models import MemoryEntry

    entries = []
    for r in records:
        owner_id = r["owner_id"]
        try:
            owner_uuid = uuid.UUID(str(owner_id))
        except (ValueError, TypeError):
            owner_uuid = owner_id

        entries.append(
            MemoryEntry(
                id=uuid.uuid4(),
                owner_id=owner_uuid,
                sender_id=r.get("sender_id"),
                sender_name=r.get("sender_name"),
                sender_role=r.get("sender_role"),
                memory_type=r.get("memory_type"),
                content=r.get("content"),
                summary=r.get("summary"),
                tags=r.get("tags", []),
                importance=r.get("importance", 0.5),
            )
        )
    if entries:
        session.add_all(entries)


def _insert_memory_proposal(
    session: Session,
    *,
    owner_id: str,
    sender_id: str | None,
    sender_name: str | None,
    sender_role: str | None,
    proposed_records: list[dict[str, Any]],
    risk_level: RiskLevel,
    reason: str,
) -> str:
    import uuid
    from backend.db.models import MemoryUpdateProposal, PendingApproval

    try:
        owner_uuid = uuid.UUID(str(owner_id))
    except (ValueError, TypeError):
        owner_uuid = owner_id

    prop_id = uuid.uuid4()
    obj = MemoryUpdateProposal(
        id=prop_id,
        owner_id=owner_uuid,
        target_table="memory_entries",
        proposed_content=json.loads(json.dumps(proposed_records, default=str)),
        risk_level=risk_level,
        reason=reason,
        status="pending",
    )
    session.add(obj)
    session.flush()

    existing_pending = (
        session.query(PendingApproval).filter(PendingApproval.proposal_id == prop_id).first()
    )
    if existing_pending is None:
        preview = ""
        if proposed_records:
            first_record = proposed_records[0]
            preview = str(first_record.get("summary") or first_record.get("content") or "")[:200]

        session.add(
            PendingApproval(
                id=uuid.uuid4(),
                owner_id=owner_uuid,
                title=f"Memory update requires approval ({risk_level} risk)",
                sender=sender_name or "Unknown",
                preview=preview,
                proposal_type="memory",
                risk_level=risk_level,
                status="pending",
                proposal_id=prop_id,
            )
        )
    return str(prop_id)


# ────────────────────────────────────────────────────────
# RISK + MEMORY BUILDING
# ────────────────────────────────────────────────────────


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    for item in items:
        norm = _normalize_text(item)
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)

    return out


def _build_memory_records(
    *,
    owner_id: str,
    sender_id: str | None,
    sender_name: str | None,
    sender_role: str | None,
    extracted: MemoryUpdateExtraction,
) -> list[dict[str, Any]]:
    now = _utcnow_iso()
    records: list[dict[str, Any]] = []

    def add_items(items: list[str], memory_type: str, importance: float):
        for item in _dedupe_keep_order(items):
            records.append(
                {
                    "owner_id": owner_id,
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "sender_role": sender_role,
                    "memory_type": memory_type,
                    "content": item,
                    "summary": item[:180],
                    "tags": [memory_type, sender_role or "unknown"],
                    "importance": importance,
                    "created_at": now,
                }
            )

    add_items(extracted.preferences, "preference", 0.85)
    add_items(extracted.constraints, "constraint", 0.90)
    add_items(extracted.followups, "follow_up", 0.75)
    add_items(extracted.decisions, "decision", 0.88)
    add_items(extracted.relationship, "relationship_signal", 0.70)

    return records


def _calculate_risk(records: list[dict[str, Any]]) -> RiskLevel:
    if not records:
        return "low"

    joined = " ".join(_normalize_text(r.get("content", "")).lower() for r in records)

    high_markers = [
        "contract",
        "legal",
        "confidential",
        "nda",
        "price change",
        "margin",
        "discount",
        "payment terms",
        "bank",
        "invoice amount",
    ]
    medium_markers = [
        "prefer",
        "preference",
        "always",
        "never",
        "must",
        "require",
        "follow up",
        "commit",
        "agreed",
        "decision",
    ]

    if any(marker in joined for marker in high_markers):
        return "high"

    if any(marker in joined for marker in medium_markers):
        return "medium"

    return "low"


def _maybe_refresh_sender_summary(
    session: Session,
    *,
    owner_id: str,
    conversation_thread_id: str | None,
    sender_external_id: str | None,
    sender_name: str | None,
    sender_role: str | None,
) -> dict[str, Any] | None:
    if not conversation_thread_id or not sender_external_id:
        return None

    from backend.db.models import ConversationSenderMemory

    try:
        owner_uuid = uuid.UUID(owner_id)
        thread_uuid = uuid.UUID(conversation_thread_id)
    except (ValueError, TypeError):
        return None

    memory_row = (
        session.query(ConversationSenderMemory)
        .filter(
            ConversationSenderMemory.owner_id == owner_uuid,
            ConversationSenderMemory.conversation_thread_id == thread_uuid,
            ConversationSenderMemory.sender_external_id == sender_external_id,
        )
        .first()
    )
    if memory_row is None:
        return None

    threshold = get_sender_summary_threshold(session, owner_id=owner_id)
    count_since_update = int(memory_row.message_count_since_update or 0)
    if count_since_update < threshold:
        return {
            "summary_refreshed": False,
            "message_count_since_update": count_since_update,
            "threshold": threshold,
        }

    recent_messages = get_recent_thread_messages(
        session,
        owner_id=owner_id,
        conversation_thread_id=conversation_thread_id,
        limit=30,
    )

    message_lines: list[str] = []
    for msg in recent_messages:
        direction = (msg.direction or "").lower()
        role = "Sender" if direction == "inbound" else "Business"
        message_lines.append(f"{role}: {msg.content}")

    prompt = SENDER_SUMMARY_PROMPT.format(
        previous_summary=memory_row.summary or "",
        messages="\n".join(message_lines) if message_lines else "No recent messages.",
    )

    llm = get_chat_llm(scope="memory", temperature=0.0)
    summary_text = _normalize_text(getattr(llm.invoke(prompt), "content", ""))

    if not summary_text:
        return {
            "summary_refreshed": False,
            "message_count_since_update": count_since_update,
            "threshold": threshold,
            "reason": "llm_empty_summary",
        }

    memory_row.summary = summary_text
    memory_row.sender_name = sender_name or memory_row.sender_name
    memory_row.sender_role = sender_role or memory_row.sender_role
    memory_row.message_count_since_update = 0
    memory_row.last_summarized_at = datetime.now(timezone.utc)
    memory_row.updated_at = datetime.now(timezone.utc)
    session.flush()

    return {
        "summary_refreshed": True,
        "message_count_since_update": 0,
        "threshold": threshold,
    }


# ────────────────────────────────────────────────────────
# READ MODE
# ────────────────────────────────────────────────────────


def memory_read_node(task: SubTask) -> dict[str, list[dict[str, Any]]]:
    completed_task = dict(task)
    session = SessionLocal()

    try:
        description = _normalize_text(task.get("description", ""))
        owner_id = _get_owner_id_from_state(task)
        sender_id = _get_sender_id_from_state(task)
        sender_role = _get_sender_role_from_state(task)

        if not owner_id:
            completed_task["status"] = "failed"
            completed_task["result"] = (
                "Memory read failed: missing owner_id in task/injected_context."
            )
            return {"completed_tasks": [completed_task]}

        if not description:
            completed_task["status"] = "failed"
            completed_task["result"] = "Memory read failed: missing task description."
            return {"completed_tasks": [completed_task]}

        messages = _search_messages(session, owner_id, description, sender_id, sender_role)
        memories = _search_memory_entries(session, owner_id, description, sender_id, sender_role)

        retrieved_records = _format_retrieved_records(messages, memories)

        llm = _get_llm()
        structured_llm = llm.with_structured_output(MemoryReadSummary)

        prompt = MEMORY_READ_PROMPT.format(
            task_description=description,
            retrieved_records=retrieved_records,
        )

        summary_raw = structured_llm.invoke(prompt)
        if isinstance(summary_raw, MemoryReadSummary):
            summary = summary_raw
        elif isinstance(summary_raw, dict):
            summary = MemoryReadSummary.model_validate(summary_raw)
        else:
            summary = MemoryReadSummary.model_validate(cast(BaseModel, summary_raw).model_dump())

        result_text = _json_dump(summary.model_dump())

        agent_response = AgentResponse(
            status="success",
            confidence="high",
            result=result_text,
            facts=[],
            unknowns=[],
            constraints=[],
        )

        completed_task["status"] = "completed"
        completed_task["result"] = agent_response.model_dump_json()

        return {"completed_tasks": [completed_task]}

    except Exception as exc:
        logger.exception("Memory read agent failed")
        agent_response = AgentResponse(
            status="failed",
            confidence="low",
            result=f"Memory read error: {exc}",
            unknowns=[str(exc)],
        )
        completed_task["status"] = "failed"
        completed_task["result"] = agent_response.model_dump_json()
        return {"completed_tasks": [completed_task]}

    finally:
        session.close()


# ────────────────────────────────────────────────────────
# UPDATE MODE
# ────────────────────────────────────────────────────────


def memory_update_node(state: dict[str, Any]) -> dict[str, Any]:
    session = SessionLocal()
    try:
        owner_id = _get_owner_id_from_state(state)
        sender_id = _get_sender_id_from_state(state)
        sender_role = _get_sender_role_from_state(state)
        sender_name = _get_sender_name_from_state(state)
        conversation_thread_id = _get_conversation_thread_id_from_state(state)

        raw_message = _normalize_text(state.get("raw_message", ""))
        reply_text = _normalize_text(state.get("reply_text", ""))
        completed_tasks_summary = _safe_completed_tasks_summary(state)

        if not owner_id:
            return {
                "memory_updates": {
                    "status": "failed",
                    "error": "Missing owner_id in pipeline state.",
                    "count": 0,
                }
            }

        if not raw_message and not reply_text:
            return {
                "memory_updates": {
                    "status": "completed",
                    "message": "No interaction content to extract.",
                    "count": 0,
                }
            }

        if (sender_role or "").lower() == "owner":
            from backend.db.models import Profile

            try:
                owner_uuid = __import__("uuid").UUID(str(owner_id))
            except Exception:
                owner_uuid = owner_id
            profile = session.query(Profile).filter(Profile.id == owner_uuid).first()
            if profile:
                business_desc = profile.business_description or ""
                prev_mem = profile.memory_context or ""

                llm = get_chat_llm(scope="memory", temperature=0.0)
                prompt = OWNER_MEMORY_UPDATE_PROMPT.format(
                    business_description=business_desc,
                    previous_memory=prev_mem,
                    raw_message=raw_message,
                    reply_text=reply_text,
                    completed_tasks_summary=completed_tasks_summary,
                )
                updated_memory = _normalize_text(getattr(llm.invoke(prompt), "content", ""))
                if updated_memory:
                    profile.memory_context = updated_memory
                    profile.updated_at = datetime.now(timezone.utc)
                    session.commit()
                    return {
                        "memory_updates": {
                            "status": "completed",
                            "message": "Owner long-term memory updated and compacted.",
                            "count": 1,
                            "persisted_to": "profiles.memory_context",
                        }
                    }

        sender_summary_update = None
        if (sender_role or "").lower() != "owner":
            sender_summary_update = _maybe_refresh_sender_summary(
                session,
                owner_id=owner_id,
                conversation_thread_id=conversation_thread_id,
                sender_external_id=sender_id,
                sender_name=sender_name,
                sender_role=sender_role,
            )

        llm = get_chat_llm(scope="memory", temperature=0.0)
        structured_llm = llm.with_structured_output(MemoryUpdateExtraction)

        prompt = MEMORY_UPDATE_PROMPT.format(
            sender_name=sender_name or "Unknown",
            sender_role=sender_role or "Unknown",
            sender_id=sender_id or "Unknown",
            raw_message=raw_message,
            reply_text=reply_text,
            completed_tasks_summary=completed_tasks_summary,
        )

        extracted_raw = structured_llm.invoke(prompt)
        if isinstance(extracted_raw, MemoryUpdateExtraction):
            extracted = extracted_raw
        elif isinstance(extracted_raw, dict):
            extracted = MemoryUpdateExtraction.model_validate(extracted_raw)
        else:
            extracted = MemoryUpdateExtraction.model_validate(
                cast(BaseModel, extracted_raw).model_dump()
            )

        records = _build_memory_records(
            owner_id=owner_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_role=sender_role,
            extracted=extracted,
        )

        if not records:
            session.commit()
            return {
                "memory_updates": {
                    "status": "completed",
                    "message": "No durable memory extracted.",
                    "count": 0,
                    "risk_level": "low",
                    "persisted_to": None,
                    "sender_summary": sender_summary_update,
                }
            }

        risk_level = _calculate_risk(records)

        if risk_level == "low":
            _insert_memory_entries(session, records)
            session.commit()

            return {
                "memory_updates": {
                    "status": "completed",
                    "count": len(records),
                    "risk_level": risk_level,
                    "persisted_to": "memory_entries",
                    "records": records,
                    "sender_summary": sender_summary_update,
                }
            }

        proposal_id = _insert_memory_proposal(
            session,
            owner_id=owner_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_role=sender_role,
            proposed_records=records,
            risk_level=risk_level,
            reason="Extracted durable memory requires owner approval before insertion.",
        )
        session.commit()

        return {
            "memory_updates": {
                "status": "completed",
                "count": len(records),
                "risk_level": risk_level,
                "persisted_to": "memory_update_proposals",
                "proposal_id": proposal_id,
                "records": records,
                "sender_summary": sender_summary_update,
            }
        }

    except Exception as exc:
        session.rollback()
        logger.exception("Memory update agent failed")
        return {
            "memory_updates": {
                "status": "failed",
                "error": str(exc),
                "count": 0,
            }
        }

    finally:
        session.close()
