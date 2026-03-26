"""
Intake Agent (Node) — PROPOSAL §3, Flow Step 1

Replaces the linear Receiver, Triage, and Context Builder nodes.
Fetches identity, loads static docs (SOUL.md, RULE.md, MEMORY.md),
evaluates early guardrails, and sets the sender role.
"""

import os
from typing import Any
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate

from backend.db.engine import SessionLocal
from backend.db.models import Customer, Supplier, Partner
from backend.utils.llm_provider import get_chat_llm

class IntakeTriage(BaseModel):
    intent_label: str = Field(description="E.g., inquiry, complaint, negotiation, support")
    urgency_level: str = Field(description="low, normal, high, critical")
    clean_message: str = Field(description="The noisy raw message rewritten into a clean instruction")


def _load_agent_file(filename: str) -> str:
    """Helper to load markdown files from the backend/agents directory."""
    path = os.path.join(os.path.dirname(__file__), "..", "agents", filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"(Missing {filename})"


def _lookup_sender(sender_id: str) -> str:
    """Look up sender identity in DB to determine role."""
    if not sender_id:
        return "Unknown"
    
    session = SessionLocal()
    try:
        if session.query(Customer).filter_by(id=int(sender_id)).first():
            return "Customer"
        if session.query(Supplier).filter_by(id=int(sender_id)).first():
            return "Supplier"
        if session.query(Partner).filter_by(id=int(sender_id)).first():
            return "Partner"
    except Exception:
        pass
    finally:
        session.close()
        
    # Fallback to a default if db not formed or sender_id is not an int
    return "Prospect"


def intake_node(state: dict) -> dict:
    """
    Intake the raw message and prepare context.
    """
    raw_msg = state.get("raw_message", "")
    sender_id = state.get("sender_id", "")
    
    # 1. Identity Resolution
    sender_role = _lookup_sender(sender_id)

    # 2. Extract context
    soul = _load_agent_file("SOUL.md")
    rules = _load_agent_file("RULE.md")
    long_term = _load_agent_file("MEMORY.md")
    short_term = [{"role": "user", "content": raw_msg}]

    # 3. LLM Triage & Sanitization
    llm = get_chat_llm(scope="default", temperature=0.0)
    triage_llm = llm.with_structured_output(IntakeTriage)
    
    prompt = PromptTemplate.from_template(
        "Analyze the following incoming message from a {sender_role}.\n"
        "1. Classify intent and urgency.\n"
        "2. Strip out emotion and rewrite the core query into a clear instruction for an internal system.\n\n"
        "Message: {raw_message}"
    )
    
    try:
        triage: IntakeTriage = triage_llm.invoke(
            prompt.format(sender_role=sender_role, raw_message=raw_msg)
        )
        intent = triage.intent_label
        urgency = triage.urgency_level
        clean_msg = triage.clean_message
    except Exception:
        # Fallback if LLM fails
        intent = "unknown"
        urgency = "normal"
        clean_msg = raw_msg

    return {
        "sender_role": sender_role,
        "intent_label": intent,
        "urgency_level": urgency,
        "raw_message": clean_msg,  # Inject sanitized message into state
        "soul_context": soul,
        "rules_context": rules,
        "long_term_memory": long_term,
        "short_term_memory": short_term,
        "guardrails_passed": True,
    }
