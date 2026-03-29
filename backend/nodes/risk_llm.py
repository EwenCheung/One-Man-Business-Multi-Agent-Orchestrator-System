"""
Risk LLM Second Pass — Semantic Evaluation Layer

Implements the optional Layer 2 LLM review that catches semantic risks
regex patterns cannot detect:
    - Implied commitments expressed in natural language
    - Factual contradictions between the reply and sub-agent findings
    - Contextual liability without explicit legal keywords
    - Intent mismatch (e.g. dismissive reply to a complaint)
    - Tone nuances beyond the four predefined labels

Only fires for MEDIUM results from the rule-based Layer 1.
Falls back silently to ([], current_level) on any LLM error so the
deterministic rule-based result is always preserved.
"""

from __future__ import annotations

import logging

from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from backend.nodes.risk_rules import (
    TaskRecord,
    format_completed_tasks_summary,
    format_existing_flags,
    _normalize_text,
)

logger = logging.getLogger(__name__)


class RiskJudgement(BaseModel):
    """Structured output from the LLM second-pass risk reviewer."""

    additional_flags: list[str] = Field(
        default_factory=list,
        description=(
            "New risk flags not already detected by the rule-based scanner. "
            "Each entry should begin with a category label "
            "(e.g. 'IMPLIED COMMITMENT: ...', 'FACTUAL CONTRADICTION: ...')."
        ),
    )
    revised_risk_level: str = Field(
        description=(
            "Final risk assessment after LLM review. "
            "Must be exactly 'high', 'medium', or 'low'."
        )
    )
    reasoning: str = Field(
        description=(
            "One to three sentences summarising the overall risk judgement "
            "and the rationale for any revision to the rule-based level."
        )
    )


_RISK_LLM_PROMPT = """\
You are a risk evaluator for a one-person business's automated reply system.
The rule-based scanner has classified this reply as {current_level} risk.
Your job is to catch semantic risks that keyword patterns cannot detect.

SENDER CONTEXT
──────────────
Role     : {sender_role}
Intent   : {intent_label}
Urgency  : {urgency_level}

VERIFIED SUB-AGENT FINDINGS
────────────────────────────
{completed_tasks_summary}

CANDIDATE REPLY
───────────────
{reply_text}

RULE-BASED FLAGS ALREADY DETECTED
──────────────────────────────────
{existing_flags_text}

YOUR TASK
─────────
Review the reply for risks the rule-based scanner may have missed. Focus on:

1. Implied commitments  — promises made through implication, not explicit keywords.
   Example: "I'll make sure this gets sorted" carries an implicit promise.

2. Factual contradictions — the reply asserts something that conflicts with the
   sub-agent findings listed above (e.g. claims a price or delivery date that
   was not confirmed or was explicitly contradicted).

3. Contextual liability — statements that could create legal responsibility
   or set a harmful precedent, even if no legal keyword is present.

4. Intent mismatch — does the reply adequately address a '{intent_label}' from
   a '{sender_role}'? A dismissive or minimising response to a complaint
   or legal matter is itself a risk.

5. Tone nuances — issues beyond the four predefined labels (over-apologetic,
   over-committed, defensive, speculative): e.g. condescending, pressuring,
   inappropriately casual for context, or misleadingly optimistic.

IMPORTANT RULES:
- Do NOT re-flag issues already listed in the rule-based flags above.
- Only flag genuine, material risks — not minor stylistic preferences.
- Prefix each new flag with a short category label
  (e.g. "IMPLIED COMMITMENT: ...", "FACTUAL CONTRADICTION: ...").
- If no new risks are found, return an empty additional_flags list.
- revised_risk_level must be exactly one of: "high", "medium", "low".
  Upgrade to high ONLY for a genuinely severe new risk.
  Downgrade to low ONLY if all rule-based flags are clear false positives
  AND the reply is demonstrably safe.
  Default: maintain "{current_level}" unless evidence clearly warrants a change.
"""


def llm_second_pass(
    reply_text: str,
    sender_role: str,
    intent_label: str,
    urgency_level: str,
    completed_tasks: list[TaskRecord],
    existing_flags: list[str],
    current_level: str,
) -> tuple[list[str], str]:
    """LLM-assisted second pass for borderline MEDIUM-risk replies.

    Catches semantic risks that rule-based patterns cannot detect:
    implied commitments, factual contradictions, contextual liability,
    and intent mismatch.

    Triggers only for MEDIUM results from the rule-based layer.
    Falls back silently to ([], current_level) on any LLM error so the
    rule-based result is always preserved.
    """
    formatted = PromptTemplate.from_template(_RISK_LLM_PROMPT).format(
        sender_role=sender_role,
        intent_label=intent_label or "unknown",
        urgency_level=urgency_level or "normal",
        completed_tasks_summary=format_completed_tasks_summary(completed_tasks),
        reply_text=reply_text,
        existing_flags_text=format_existing_flags(existing_flags),
        current_level=current_level,
    )

    try:
        from backend.utils.llm_provider import get_chat_llm  # noqa: PLC0415 — deferred to avoid Settings() at import time

        llm = get_chat_llm(temperature=0.0)
        judgement: RiskJudgement = llm.with_structured_output(RiskJudgement).invoke(formatted)

        revised = _normalize_text(judgement.revised_risk_level)
        if revised not in {"high", "medium", "low"}:
            revised = current_level

        additional = [f"LLM: {f}" for f in judgement.additional_flags if f.strip()]
        if judgement.reasoning:
            logger.info("LLM risk reasoning: %s", judgement.reasoning)
        return additional, revised

    except Exception as exc:
        logger.warning(
            "RiskNode LLM second pass failed — %s. Preserving rule-based result.", exc
        )
        return [], current_level
