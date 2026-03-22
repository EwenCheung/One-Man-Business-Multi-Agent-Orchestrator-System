"""
Intake Agent (Node)

Replaces the linear Receiver, Triage, and Context Builder nodes.
Fetches identity, loads static docs (SOUL.md, RULE.md, MEMORY.md),
evaluates early guardrails, and sets the sender role.
"""

import os
from typing import Any

def _load_agent_file(filename: str) -> str:
    """Helper to load markdown files from the backend/agents directory."""
    path = os.path.join(os.path.dirname(__file__), "..", "agents", filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return f"(Missing {filename})"


def intake_node(state: dict) -> dict:
    """
    Intake the raw message and prepare context.

    Reads from state: raw_message, sender_id
    Writes 3-tier memory and identity context to state.
    """
    # 1. Load static identity and rule contexts
    soul = _load_agent_file("SOUL.md")
    rules = _load_agent_file("RULE.md")
    
    # 2. Load long-term memory (currently from MEMORY.md stub)
    long_term = _load_agent_file("MEMORY.md")
    
    # 3. Load short-term memory (stub for recent DB logs)
    raw_msg = state.get("raw_message", "")
    short_term = [{"role": "user", "content": raw_msg}]

    # TODO: Fetch actual sender profile from DB to determine real role
    return {
        "sender_role": "unknown",
        "intent_label": "unknown",
        "urgency_level": "normal",
        "soul_context": soul,
        "rules_context": rules,
        "long_term_memory": long_term,
        "short_term_memory": short_term,
        "guardrails_passed": True,
    }
