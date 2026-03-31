"""
Risk Node — Pipeline Entry Point

Wires the rule-based checkers (risk_rules) and the optional LLM second
pass (risk_llm) into a single LangGraph node function.

See risk_rules.py for the deterministic Layer 1 evaluation.
See risk_llm.py for the semantic Layer 2 LLM review.
"""

from __future__ import annotations

import logging

from backend.nodes.risk_llm import llm_second_pass
from backend.nodes.risk_rules import (
    TaskRecord,
    aggregate_risk,
    check_confidence,
    check_disclosure,
    check_escalation_triggers,
    check_intent_urgency,
    check_pii_leakage,
    check_policy_cross,
    check_role_sensitivity,
    check_tone,
    check_unverified_claims,
    scan_for_risky_keywords,
)

logger = logging.getLogger(__name__)


def risk_node(state: dict) -> dict:
    """
    Evaluate risk of the generated reply and decide approval requirements.

    Reads from state:
        - reply_text         (str)       — candidate reply from the Reply Agent
        - sender_role        (str)       — role of the message sender
        - completed_tasks    (list)      — sub-agent results for cross-checking
        - confidence_level   (str)       — 'high' | 'medium' | 'low' from Reply Agent
        - confidence_note    (str)       — human-readable confidence summary
        - unverified_claims  (list[str]) — hedged statements self-reported by Reply Agent
        - tone_flags         (list[str]) — tone anomalies self-reported by Reply Agent
        - intent_label       (str)       — classified intent of the original message
        - urgency_level      (str)       — urgency classification of the original message

    Writes to state:
        - risk_level         ('low' | 'medium' | 'high')
        - risk_flags         (list[str]) — human-readable reasons for the assessment
        - requires_approval  (bool)      — True if owner must review before sending
    """
    reply_text: str = state.get("reply_text", "")
    sender_role: str = state.get("sender_role", "unknown")
    completed_tasks: list[TaskRecord] = state.get("completed_tasks", [])
    confidence_level: str = state.get("confidence_level", "")
    confidence_note: str = state.get("confidence_note", "")
    unverified_claims: list[str] = state.get("unverified_claims", [])
    tone_flags: list[str] = state.get("tone_flags", [])
    intent_label: str = state.get("intent_label", "")
    urgency_level: str = state.get("urgency_level", "")

    flags = []
    flags.extend(scan_for_risky_keywords(reply_text))
    flags.extend(check_disclosure(reply_text, sender_role))
    flags.extend(check_escalation_triggers(reply_text))
    flags.extend(check_pii_leakage(reply_text))               # ← PII / credentials
    flags.extend(check_role_sensitivity(reply_text, sender_role))  # ← role thresholds
    flags.extend(check_policy_cross(completed_tasks))
    flags.extend(check_unverified_claims(reply_text, completed_tasks))
    flags.extend(check_confidence(confidence_level, confidence_note, unverified_claims))
    flags.extend(check_tone(tone_flags))
    flags.extend(check_intent_urgency(intent_label, urgency_level))

    risk_level, requires_approval = aggregate_risk(flags)

    # ── LLM second pass (borderline MEDIUM cases only) ────────────────────────
    if risk_level == "medium":
        additional_flags, revised_level = llm_second_pass(
            reply_text=reply_text,
            sender_role=sender_role,
            intent_label=intent_label,
            urgency_level=urgency_level,
            completed_tasks=completed_tasks,
            existing_flags=flags,
            current_level=risk_level,
        )
        if additional_flags:
            flags.extend(additional_flags)
            logger.info("LLM second pass added %d flag(s)", len(additional_flags))
        if revised_level != risk_level:
            logger.info(
                "LLM second pass revised risk: %s → %s", risk_level, revised_level
            )
            risk_level = revised_level
            requires_approval = revised_level != "low"

    logger.info(
        "Risk evaluation complete — level=%s, flags=%d, approval=%s",
        risk_level, len(flags), requires_approval,
    )
    for flag in flags:
        logger.info("  risk_flag: %s", flag)

    return {
        "risk_level": risk_level,
        "risk_flags": flags,
        "requires_approval": requires_approval,
    }
