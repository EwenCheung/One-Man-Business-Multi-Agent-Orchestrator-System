from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.db.engine import SessionLocal
from backend.graph.state import SubTask
from backend.models.agent_response import AgentResponse
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


def _get_owner_id_from_state(state: dict) -> str | None:
    if state.get("owner_id"):
        return str(state["owner_id"])

    injected = state.get("injected_context", {}) or {}
    if injected.get("owner_id"):
        return str(injected["owner_id"])

    return None


def _get_sender_id_from_state(state: dict) -> str | None:
    if state.get("sender_id"):
        return str(state["sender_id"])

    injected = state.get("injected_context", {}) or {}
    if injected.get("sender_id"):
        return str(injected["sender_id"])

    return None


def _get_sender_role_from_state(state: dict) -> str | None:
    if state.get("sender_role"):
        return str(state["sender_role"])

    injected = state.get("injected_context", {}) or {}
    if injected.get("sender_role"):
        return str(injected["sender_role"])

    return None


def _get_sender_name_from_state(state: dict) -> str | None:
    if state.get("sender_name"):
        return str(state["sender_name"])

    injected = state.get("injected_context", {}) or {}
    if injected.get("sender_name"):
        return str(injected["sender_name"])

    return None


def _safe_completed_tasks_summary(state: dict) -> str:
    completed_tasks = state.get("completed_tasks", [])
    if not completed_tasks:
        return ""

    parts: list[str] = []
    for task in completed_tasks:
        task_id = task.get("task_id", "?")
        assignee = task.get("assignee", "?")
        result = _normalize_text(task.get("result", ""))
        parts.append(f"Task {task_id} ({assignee}): {result}")
    return "\n".join(parts)


# ────────────────────────────────────────────────────────
# DB ACCESS — READ MODE
# ────────────────────────────────────────────────────────

def _search_messages(session, owner_id: str, query: str, sender_id: str | None = None) -> list[dict[str, Any]]:
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

    if sender_id:
        sql += " AND (sender_id = :sender_id OR sender_id IS NULL)"
        params["sender_id"] = sender_id

    sql += " ORDER BY created_at DESC LIMIT 8"

    rows = session.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _search_memory_entries(session, owner_id: str, query: str, sender_id: str | None = None) -> list[dict[str, Any]]:
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

    if sender_id:
        sql += " AND (sender_id = :sender_id OR sender_id IS NULL)"
        params["sender_id"] = sender_id

    sql += " ORDER BY created_at DESC LIMIT 8"

    rows = session.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _format_retrieved_records(messages: list[dict[str, Any]], memories: list[dict[str, Any]]) -> str:
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

def _insert_memory_entries(session, records: list[dict[str, Any]]) -> None:
    sql = text("""
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
            :created_at
        )
    """)

    for record in records:
        session.execute(sql, record)


def _insert_memory_proposal(
    session,
    *,
    owner_id: str,
    sender_id: str | None,
    sender_name: str | None,
    sender_role: str | None,
    proposed_records: list[dict[str, Any]],
    risk_level: RiskLevel,
    reason: str,
) -> str:
    sql = text("""
        INSERT INTO public.memory_update_proposals (
            owner_id,
            sender_id,
            sender_name,
            sender_role,
            target_table,
            proposed_content,
            risk_level,
            reason,
            status,
            created_at
        )
        VALUES (
            :owner_id,
            :sender_id,
            :sender_name,
            :sender_role,
            'memory_entries',
            CAST(:proposed_content AS jsonb),
            :risk_level,
            :reason,
            'pending',
            now()
        )
        RETURNING id
    """)

    row = session.execute(
        sql,
        {
            "owner_id": owner_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_role": sender_role,
            "proposed_content": json.dumps(proposed_records, default=str),
            "risk_level": risk_level,
            "reason": reason,
        },
    ).fetchone()

    return str(row[0])


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


# ────────────────────────────────────────────────────────
# READ MODE
# ────────────────────────────────────────────────────────

def memory_read_node(task: SubTask) -> dict:
    completed_task = dict(task)
    session = SessionLocal()

    try:
        description = _normalize_text(task.get("description", ""))
        owner_id = _get_owner_id_from_state(task)
        sender_id = _get_sender_id_from_state(task)

        if not owner_id:
            completed_task["status"] = "failed"
            completed_task["result"] = "Memory read failed: missing owner_id in task/injected_context."
            return {"completed_tasks": [completed_task]}

        if not description:
            completed_task["status"] = "failed"
            completed_task["result"] = "Memory read failed: missing task description."
            return {"completed_tasks": [completed_task]}

        messages = _search_messages(session, owner_id, description, sender_id)
        memories = _search_memory_entries(session, owner_id, description, sender_id)

        retrieved_records = _format_retrieved_records(messages, memories)

        llm = _get_llm()
        structured_llm = llm.with_structured_output(MemoryReadSummary)

        prompt = MEMORY_READ_PROMPT.format(
            task_description=description,
            retrieved_records=retrieved_records,
        )

        summary = structured_llm.invoke(prompt)

        result_text = _json_dump(summary.model_dump())
        
        agent_response = AgentResponse(
            status="success",
            confidence="high",
            result=result_text,
            facts=[],
            unknowns=[],
            constraints=[]
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
            unknowns=[str(exc)]
        )
        completed_task["status"] = "failed"
        completed_task["result"] = agent_response.model_dump_json()
        return {"completed_tasks": [completed_task]}

    finally:
        session.close()


# ────────────────────────────────────────────────────────
# UPDATE MODE
# ────────────────────────────────────────────────────────

def memory_update_node(state: dict) -> dict:
    session = SessionLocal()
    try:
        owner_id = _get_owner_id_from_state(state)
        sender_id = _get_sender_id_from_state(state)
        sender_role = _get_sender_role_from_state(state)
        sender_name = _get_sender_name_from_state(state)

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

        extracted = structured_llm.invoke(prompt)

        records = _build_memory_records(
            owner_id=owner_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_role=sender_role,
            extracted=extracted,
        )

        if not records:
            return {
                "memory_updates": {
                    "status": "completed",
                    "message": "No durable memory extracted.",
                    "count": 0,
                    "risk_level": "low",
                    "persisted_to": None,
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
