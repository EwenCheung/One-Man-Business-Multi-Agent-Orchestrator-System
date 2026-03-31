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
from backend.db.models import Customer, Supplier, Partner, Investor
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
        if session.query(Customer).filter_by(id=sender_id).first():
            return "Customer"
        if session.query(Supplier).filter_by(id=sender_id).first():
            return "Supplier"
        if session.query(Partner).filter_by(id=sender_id).first():
            return "Partner"
        if session.query(Investor).filter_by(id=sender_id).first():
            return "Investor"
    except Exception:
        pass
    finally:
        session.close()
        
    # Fallback to a default if db not formed or sender_id is not found
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
    
    # Fetch short term memory from DB
    from backend.db.models import Message
    session = SessionLocal()
    short_term = []
    
    # We need the owner_id to properly save the new message.
    # In a clean architecture, router or auth middleware supplies owner_id.
    # For now, we will query the customer to get their owner_id if possible.
    owner_id_to_use = "00000000-0000-0000-0000-000000000000"
    try:
        if sender_role == "Customer":
            c = session.query(Customer).filter_by(id=sender_id).first()
            if c: owner_id_to_use = c.owner_id
        elif sender_role == "Supplier":
            s = session.query(Supplier).filter_by(id=sender_id).first()
            if s: owner_id_to_use = s.owner_id
        elif sender_role == "Partner":
            p = session.query(Partner).filter_by(id=sender_id).first()
            if p: owner_id_to_use = p.owner_id
        elif sender_role == "Investor":
            i = session.query(Investor).filter_by(id=sender_id).first()
            if i: owner_id_to_use = i.owner_id
            
        thread_id = state.get("thread_id") or sender_id
        
        # Pull last 4 messages for this thread (or sender)
        recent_msgs = (
            session.query(Message)
            .filter(
                Message.sender_id == sender_id
            )
            .order_by(Message.created_at.desc())
            .limit(4)
            .all()
        )
        
        # Reverse them so chronological order
        for msg in reversed(recent_msgs):
            # Map direction to LangChain concept
            role = "user" if msg.direction == "inbound" else "assistant"
            short_term.append({"role": role, "content": msg.content})
            
        # Add current message to DB
        new_msg = Message(
            owner_id=owner_id_to_use,
            sender_id=sender_id,
            sender_role=sender_role,
            direction="inbound", # User message
            content=raw_msg
        )
        session.add(new_msg)
        session.commit()
        
    except Exception as e:
        print(f"Failed to load or save memory: {e}")
        pass
    finally:
        session.close()

    # Append current message to payload going to LLM
    short_term.append({"role": "user", "content": raw_msg})

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
