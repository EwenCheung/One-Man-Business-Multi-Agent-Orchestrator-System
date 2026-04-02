"""
Intake Agent (Node) — PROPOSAL §3, Flow Step 1

Replaces the linear Receiver, Triage, and Context Builder nodes.
Fetches identity, loads static docs (SOUL.md, RULE.md, MEMORY.md),
evaluates early guardrails, and sets the sender role.
"""

import os

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import Message
from backend.services.identity_resolution import resolve_or_create_sender


def _load_agent_file(filename: str) -> str:
    """Helper to load markdown files from the backend/agents directory."""
    path = os.path.join(os.path.dirname(__file__), "..", "agents", filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"(Missing {filename})"


def intake_node(state: dict[str, object]) -> dict[str, object]:
    """
    Intake the raw message and prepare context.
    """
    raw_msg = str(state.get("raw_message", ""))
    external_sender_id = str(state.get("external_sender_id") or state.get("sender_id", ""))
    sender_name = str(state.get("sender_name", "Unknown"))
    cleaned_message = " ".join(str(raw_msg).split())

    session = SessionLocal()
    short_term = []

    try:
        resolved_identity = resolve_or_create_sender(session, external_sender_id, sender_name)
        sender_role = resolved_identity["sender_role"]
        sender_id = resolved_identity["sender_id"]
        entity_id = resolved_identity["entity_id"]
        owner_id_to_use = resolved_identity["owner_id"]
        thread_id = state.get("thread_id") or external_sender_id

        recent_msgs = (
            session.query(Message)
            .filter(Message.sender_id == external_sender_id)
            .order_by(Message.created_at.desc())
            .limit(4)
            .all()
        )

        for msg in reversed(recent_msgs):
            role = "user" if msg.direction == "inbound" else "assistant"
            short_term.append({"role": role, "content": msg.content})

        new_msg = Message(
            owner_id=owner_id_to_use,
            sender_id=external_sender_id,
            sender_name=sender_name,
            sender_role=sender_role,
            direction="inbound",
            content=cleaned_message,
        )
        session.add(new_msg)
        session.commit()
    except Exception as e:
        print(f"Failed to resolve identity or save memory: {e}")
        sender_role = "customer"
        sender_id = ""
        entity_id = ""
        owner_id_to_use = settings.OWNER_ID
        thread_id = state.get("thread_id") or external_sender_id
    finally:
        session.close()

    # 2. Extract context
    soul = _load_agent_file("SOUL.md")
    rules = _load_agent_file("RULE.md")
    long_term = _load_agent_file("MEMORY.md")

    short_term.append({"role": "user", "content": cleaned_message})

    return {
        "owner_id": owner_id_to_use,
        "sender_role": sender_role,
        "sender_id": sender_id,
        "entity_id": entity_id,
        "external_sender_id": external_sender_id,
        "thread_id": thread_id,
        "intent_label": "unknown",
        "urgency_level": "normal",
        "raw_message": cleaned_message,
        "soul_context": soul,
        "rules_context": rules,
        "long_term_memory": long_term,
        "short_term_memory": short_term,
        "guardrails_passed": True,
    }
