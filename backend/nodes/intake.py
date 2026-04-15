"""
Intake Agent (Node) — PROPOSAL §3, Flow Step 1

Replaces the linear Receiver, Triage, and Context Builder nodes.
Fetches identity, loads SOUL, RULE, and LONG TERM MEMORY context from the database,
evaluates early guardrails, and sets the sender role.
"""

from typing import cast

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


DEFAULT_SOUL_CONTEXT = (
    "# SOUL\n\n"
    "## Identity\n\n"
    "You are the business's owner-side operator: direct, strategic, calm, and concise. "
    "Optimize for owner benefit, clarity, and action.\n\n"
    "## Voice\n\n"
    "- Be practical and to the point.\n"
    "- Lead with the useful answer.\n"
    "- Ask or verify before promising anything uncertain.\n"
    "- Stay helpful, professional, and owner-first."
)
DEFAULT_RULES_CONTEXT = (
    "Apply conservative business-safe defaults. Do not reveal sensitive data, "
    "do not make unsupported commitments, and prefer approval for uncertain cases."
)
DEFAULT_LONG_TERM_MEMORY = "No long-term memory available."


def intake_node(state: dict[str, object]) -> dict[str, object]:
    """
    Intake the raw message and prepare context.
    """
    raw_msg = str(state.get("raw_message", ""))
    external_sender_id = str(state.get("external_sender_id") or state.get("sender_id", ""))
    owner_id = str(state.get("owner_id") or settings.OWNER_ID)
    sender_name = str(state.get("sender_name", "Unknown"))
    telegram_username = state.get("telegram_username")
    telegram_chat_id = state.get("telegram_chat_id")
    telegram_contact_phone = state.get("telegram_contact_phone")

    aliases: list[str] = []
    if telegram_username:
        aliases.append(cast(str, telegram_username))
    if telegram_contact_phone:
        aliases.append(str(telegram_contact_phone))

    cleaned_message = " ".join(str(raw_msg).split())
    session = SessionLocal()
    short_term: list[dict[str, str]] = []
    sender_memory = ""
    long_term = ""
    conversation_thread_id = ""

    try:
        requested_thread_id = str(state.get("thread_id") or "").strip() or None

        try:
            if aliases or telegram_username or telegram_chat_id:
                resolved_identity = resolve_or_create_sender(
                    session,
                    external_sender_id,
                    sender_name,
                    aliases=aliases if aliases else None,
                    telegram_username=str(telegram_username) if telegram_username else None,
                    telegram_chat_id=str(telegram_chat_id) if telegram_chat_id else None,
                    owner_id=owner_id,
                )
            else:
                resolved_identity = resolve_or_create_sender(
                    session,
                    external_sender_id,
                    sender_name,
                    owner_id=owner_id,
                )
        except TypeError:
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
            sender_channel="telegram" if str(external_sender_id).startswith("tg:") else "api",
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

        if sender_role == "owner":
            short_term = get_short_term_memory(
                session,
                owner_id=owner_id_to_use,
                conversation_thread_id=thread.id,
                limit=10,
            )
            long_term = get_long_term_owner_memory(session, owner_id=owner_id_to_use)
        else:
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
                sender_role=sender_role,
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
        long_term = DEFAULT_LONG_TERM_MEMORY
    finally:
        session.close()

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

    soul = profile_contexts["soul_context"] or DEFAULT_SOUL_CONTEXT
    rules = profile_contexts["rule_context"] or DEFAULT_RULES_CONTEXT
    if profile_contexts["memory_context"]:
        profile_memory = f"Owner Memory Context:\n{profile_contexts['memory_context']}"
        long_term = f"{profile_memory}\n\n{long_term}" if long_term else profile_memory
    if profile_contexts.get("business_description"):
        long_term = (
            f"Business Description:\n{profile_contexts['business_description']}\n\n" + long_term
        )
    if not long_term:
        long_term = DEFAULT_LONG_TERM_MEMORY
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
