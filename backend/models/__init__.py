"""
Pydantic schemas for data flowing through the pipeline.

This file contains example schemas. Add your own models here as needed.
Each pipeline stage's input/output should be defined here so the
team has a shared contract.

See AGENTS.md Sections 7.1–7.10 for the full field specs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Example: Incoming Message ─────────────────────────────────
# (Section 7.1 — Receiver input)

class IncomingMessage(BaseModel):
    """Raw incoming message from an external source."""
    raw_message: str
    sender_id: str
    sender_name: Optional[str] = None
    thread_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_type: Optional[str] = None


# ── Example: Pipeline State ──────────────────────────────────
# This mirrors the LangGraph state — see graph/state.py

class PipelineResult(BaseModel):
    """Final output returned by the API after a pipeline run."""
    reply_text: str = ""
    risk_level: str = "low"
    requires_approval: bool = False
    status: str = "completed"
    trace: dict[str, Any] = Field(default_factory=dict)


# TODO: Add more schemas as needed by each agent/node.
# Suggested models (see AGENTS.md for field details):
#   - StandardizedMessage  (Receiver output)
#   - TriageResult         (Triage output)
#   - ContextPackage       (Context Builder output)
#   - PolicyResult         (Policy Agent output)
#   - OrchestrationPlan    (Orchestrator output)
#   - RetrievalResult      (Internal Retriever output)
#   - ResearchResult       (External Research output)
#   - CandidateReply       (Reply Agent output)
#   - RiskAssessment       (Risk Node output)
#   - MemoryUpdate         (Update Agent output)
