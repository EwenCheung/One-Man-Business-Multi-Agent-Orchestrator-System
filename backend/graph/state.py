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
    description: str  # Instructions to the sub-agent
    assignee: str  # "retriever" | "research" | "policy" | "memory"
    status: str  # "pending" | "completed" | "failed"
    result: str  # Detailed output from the sub-agent
    priority: str  # "required" | "optional"
    context_needed: list[str]  # What specific global context keys the Orchestrator requested
    injected_context: dict[str, Any]  # The actual quarantine payload populated by the router


class PipelineState(TypedDict, total=False):
    """Shared state for the LangGraph pipeline."""

    # ── Input (set at the start) ──────────────────────────────
    raw_message: str
    owner_id: str
    sender_id: str
    external_sender_id: str
    entity_id: str
    trace_id: str
    sender_name: str
    thread_id: str
    conversation_thread_id: str
    source_type: str
    telegram_user_id: str
    telegram_username: str
    telegram_chat_id: str
    telegram_contact_phone: str

    # ── Intake Agent output ───────────────────────────────────
    sender_role: str
    intent_label: str
    urgency_level: str
    short_term_memory: list[dict[str, Any]]  # Recent chat history
    long_term_memory: str  # LONG TERM MEMORY summary from profile/memory services
    sender_memory: str
    soul_context: str  # SOUL context
    rules_context: str  # RULE context
    guardrails_passed: bool

    # ── Orchestrator Harness Control ──────────────────────────
    replan_count: int  # Tracks how many replan cycles have occurred
    failed_tasks: Annotated[list[SubTask], operator.add]  # Fan-in for failed tasks
    orchestrator_warnings: Annotated[list[str], operator.add]  # Guardrail breach logs

    # ── Orchestrator (Supervisor) output ──────────────────────
    plan_steps: Annotated[list[str], operator.add]
    route_to_reply: bool
    active_tasks: list[SubTask]

    # ── Sub-Agents output (Fan-in Aggregation) ────────────────
    completed_tasks: Annotated[list[SubTask], operator.add]

    # ── Reply output ──────────────────────────────────────────
    generated_reply_text: str
    reply_text: str
    confidence_note: str
    confidence_level: str
    unverified_claims: list[str]
    tone_flags: list[str]

    # ── Approval-rule validation output ────────────────────────
    approval_rule_flags: list[str]
    approval_rule_requires_approval: bool

    # ── Risk output ───────────────────────────────────────────
    risk_level: str  # "low" | "medium" | "high"
    risk_flags: list[str]
    requires_approval: bool

    # ── Risk Approval Flow ────────────────────────────────────
    held_reply_id: str  # UUID of the held reply (if risk triggered hold)

    # ── Update output ─────────────────────────────────────────
    memory_updates: list[dict[str, Any]]
