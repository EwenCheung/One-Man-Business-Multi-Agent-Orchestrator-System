"""
Intake Agent (Node) — PROPOSAL §3, Flow Step 1

Replaces the linear Receiver, Triage, and Context Builder nodes.
Fetches identity, loads static docs (SOUL.md, RULE.md, MEMORY.md),
evaluates early guardrails, and sets the sender role.
"""

import os

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.services.identity_resolution import resolve_or_create_sender
from backend.services.conversation_memory import (
    add_message_to_thread,
    build_three_layer_memory_context,
    get_long_term_owner_memory,
    get_or_create_conversation_thread,
    get_profile_contexts,
    get_short_term_memory,
    increment_sender_memory_counter,
)


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
    fallback_soul = _load_agent_file("SOUL.md")
    fallback_rules = _load_agent_file("RULE.md")
    fallback_long_term = _load_agent_file("MEMORY.md")

    session = SessionLocal()
    short_term: list[dict[str, str]] = []
    sender_memory = ""
    long_term = ""
    conversation_thread_id = ""

    try:
        requested_thread_id = str(state.get("thread_id") or "").strip() or None

        if str(state.get("sender_role", "")).lower() == "owner":
            sender_role = "owner"
            sender_id = external_sender_id
            entity_id = external_sender_id
            owner_id_to_use = settings.OWNER_ID
            thread = get_or_create_conversation_thread(
                session,
                owner_id=owner_id_to_use,
                sender_role="owner",
                external_sender_id=external_sender_id,
                sender_name=sender_name,
                requested_thread_id=requested_thread_id,
            )

            _ = add_message_to_thread(
                session,
                owner_id=owner_id_to_use,
                conversation_thread_id=thread.id,
                sender_id=external_sender_id,
                sender_name=sender_name,
                sender_role=sender_role,
                direction="inbound",
                content=cleaned_message,
            )

            short_term = get_short_term_memory(
                session,
                owner_id=owner_id_to_use,
                conversation_thread_id=thread.id,
                limit=10,
            )
            long_term = get_long_term_owner_memory(session, owner_id=owner_id_to_use)
            conversation_thread_id = str(thread.id)
            thread_id = conversation_thread_id
        else:
            resolved_identity = resolve_or_create_sender(session, external_sender_id, sender_name)
            sender_role = resolved_identity["sender_role"]
            sender_id = resolved_identity["sender_id"]
            entity_id = resolved_identity["entity_id"]
            owner_id_to_use = str(resolved_identity["owner_id"])
            thread = get_or_create_conversation_thread(
                session,
                owner_id=owner_id_to_use,
                sender_role=sender_role,
                external_sender_id=external_sender_id,
                sender_name=sender_name,
                requested_thread_id=requested_thread_id,
            )

            _ = add_message_to_thread(
                session,
                owner_id=owner_id_to_use,
                conversation_thread_id=thread.id,
                sender_id=external_sender_id,
                sender_name=sender_name,
                sender_role=sender_role,
                direction="inbound",
                content=cleaned_message,
            )

            _ = increment_sender_memory_counter(
                session,
                owner_id=owner_id_to_use,
                conversation_thread_id=thread.id,
                sender_external_id=external_sender_id,
                sender_name=sender_name,
                sender_role=sender_role,
            )

            memory_layers = build_three_layer_memory_context(
                session,
                owner_id=owner_id_to_use,
                conversation_thread_id=thread.id,
                sender_external_id=external_sender_id,
            )
            short_term_raw = memory_layers.get("short_term_memory")
            short_term = (
                [
                    {
                        "role": str(entry.get("role", "user")),
                        "content": str(entry.get("content", "")),
                    }
                    for entry in short_term_raw
                ]
                if isinstance(short_term_raw, list)
                else []
            )
            long_term = str(memory_layers.get("long_term_memory") or "")
            sender_memory = str(memory_layers.get("sender_memory") or "")
            conversation_thread_id = str(thread.id)
            thread_id = conversation_thread_id

        session.commit()
    except Exception as e:
        print(f"Failed to resolve identity or save memory: {e}")
        sender_role = "customer"
        sender_id = ""
        entity_id = ""
        owner_id_to_use = settings.OWNER_ID
        thread_id = state.get("thread_id") or external_sender_id
        long_term = fallback_long_term
    finally:
        session.close()

    # 2. Extract context
    session = SessionLocal()
    try:
        profile_contexts = get_profile_contexts(session, owner_id=owner_id_to_use)
    except Exception:
        profile_contexts = {
            "memory_context": "",
            "soul_context": "",
            "rule_context": "",
            "business_description": "",
        }
    finally:
        session.close()

    soul = profile_contexts["soul_context"] or fallback_soul
    rules = profile_contexts["rule_context"] or fallback_rules
    if profile_contexts["memory_context"]:
        long_term = profile_contexts["memory_context"]
    if profile_contexts.get("business_description"):
        long_term = (
            f"Business Description:\n{profile_contexts['business_description']}\n\n" + long_term
        )
    if not long_term:
        long_term = fallback_long_term
    if not short_term:
        short_term = [{"role": "user", "content": cleaned_message}]

    return {
        "owner_id": owner_id_to_use,
        "sender_role": sender_role,
        "sender_id": sender_id,
        "entity_id": entity_id,
        "external_sender_id": external_sender_id,
        "conversation_thread_id": conversation_thread_id,
        "thread_id": thread_id,
        "intent_label": "unknown",
        "urgency_level": "normal",
        "raw_message": cleaned_message,
        "soul_context": soul,
        "rules_context": rules,
        "long_term_memory": long_term,
        "sender_memory": sender_memory,
        "short_term_memory": short_term,
        "guardrails_passed": True,
    }
