"""
LangGraph Pipeline State (Section 6)

Defines the shared state for the Supervisor Multi-Agent architecture.
Uses Annotated lists for fan-out / fan-in aggregation.
"""

import operator
from typing import Any, TypedDict, Annotated

class SubTask(TypedDict):
    """A specifically assigned task for a sub-agent."""
    task_id: str
    description: str          # Instructions to the sub-agent
    assignee: str             # "retriever" | "research" | "policy"
    status: str               # "pending" | "completed"
    result: str               # Detailed output from the sub-agent
    sender_role: str           # "customer" | "supplier" | "investor" | "partner"
    sender_id: str             # ID of the sender (for row-level scoping)


class PipelineState(TypedDict, total=False):
    """Shared state for the LangGraph pipeline."""

    # ── Input (set at the start) ──────────────────────────────
    raw_message: str
    sender_id: str
    sender_name: str
    thread_id: str
    source_type: str

    # ── Intake Agent output ───────────────────────────────────
    sender_role: str
    intent_label: str
    urgency_level: str
    short_term_memory: list[dict[str, Any]]  # Recent chat history
    long_term_memory: str                    # Summary or MEMORY.md abstract
    soul_context: str                        # Loaded from SOUL.md
    rules_context: str                       # Loaded from RULE.md
    guardrails_passed: bool

    # ── Orchestrator (Supervisor) output ──────────────────────
    plan_steps: Annotated[list[str], operator.add]
    route_to_reply: bool
    active_tasks: list[SubTask]

    # ── Sub-Agents output (Fan-in Aggregation) ────────────────
    completed_tasks: Annotated[list[SubTask], operator.add]

    # ── Reply output ──────────────────────────────────────────
    reply_text: str
    confidence_note: str

    # ── Risk output ───────────────────────────────────────────
    risk_level: str           # "low" | "medium" | "high"
    risk_flags: list[str]
    requires_approval: bool

    # ── Update output ─────────────────────────────────────────
    memory_updates: list[dict[str, Any]]
