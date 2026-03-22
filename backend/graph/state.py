"""
LangGraph Pipeline State (Section 6)

Defines the shared state that flows through the entire pipeline graph.
Every node/agent reads from and writes to this state.

See AGENTS.md Sections 7.1–7.10 for what each field represents.
"""

from __future__ import annotations

from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    """
    Shared state for the LangGraph pipeline.

    Add fields here as you implement each agent/node.
    Each agent reads what it needs and writes its outputs back.
    """

    # ── Input (set at the start) ──────────────────────────────
    raw_message: str
    sender_id: str
    sender_name: str
    thread_id: str
    source_type: str

    # ── Receiver output ───────────────────────────────────────
    sender_role: str          # "customer" | "supplier" | "investor" | "partner" | "unknown"

    # ── Triage output ─────────────────────────────────────────
    predicted_role: str
    intent_label: str
    urgency_level: str
    needs_internal_retrieval: bool
    needs_external_research: bool
    risk_hint: str

    # ── Context Builder output ────────────────────────────────
    context: dict[str, Any]

    # ── Policy Agent output ───────────────────────────────────
    policy_constraints: dict[str, Any]
    disclosure_boundaries: list[str]

    # ── Orchestrator output ───────────────────────────────────
    plan_steps: list[str]
    orchestrator_next_step: str  # "retriever" | "research" | "policy" | "reply"
    requires_external_research: bool
    requires_approval: bool

    # ── Retriever output ──────────────────────────────────────
    retrieved_context: list[dict[str, Any]]

    # ── Research output (optional) ────────────────────────────
    research_findings: str

    # ── Reply output ──────────────────────────────────────────
    reply_text: str
    confidence_note: str

    # ── Risk output ───────────────────────────────────────────
    risk_level: str           # "low" | "medium" | "high"
    risk_flags: list[str]

    # ── Update output ─────────────────────────────────────────
    memory_updates: list[dict[str, Any]]
