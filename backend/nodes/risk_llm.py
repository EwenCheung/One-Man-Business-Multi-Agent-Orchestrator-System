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
   or legal matter is itself a risk. This applies even when the reply contains
   a factually accurate policy explanation: if the specific grievance is not
   acknowledged and the reply treats the complaint as a routine information
   request (e.g. providing return policy text + directing to T&C without
   engaging the actual concern), that IS a dismissal and IS an intent mismatch.

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
  Upgrade to "high" when you find ANY of the following:
    - Implied commitment: an unhedged delivery timeline, resolution promise, or
      guaranteed outcome (e.g. "I'll make sure this gets sorted", "you should have
      it by the weekend", "we'll find the right outcome for you").
      NOT an implied commitment:
        • A hedged estimate with an explicit confirmation caveat (e.g. "should be
          processed within 3-5 days, we'll confirm the exact timeline once in our
          system" — hedged modal + caveat = safe).
        • A response/process ETA in the context of explicit non-commitment (e.g.
          "you can expect to hear back within 1-2 business days" when the reply
          has already refused to commit to the underlying request — this is a
          logistics note about when to expect an update, not a promise about the
          outcome itself).
        • An exploratory or investigatory statement with a modal hedge (e.g.
          "I'll see what options might be available on our end" — the word "might"
          signals uncertainty; no specific outcome, price, or timeline is implied.
          "I'll see what X might be" = offer to investigate, not a guarantee).
    - Factual contradiction: the reply asserts something that conflicts with the
      sub-agent findings listed above (e.g. a delivery date, price, or availability
      claim that was not confirmed or was explicitly contradicted).
    - Contextual liability: the reply accepts fault, guarantees non-recurrence, or
      creates open-ended obligation (e.g. "this should never have happened",
      "we'll do everything in our power to make this right").
    - Intent mismatch: the reply fails to engage with a complaint and instead
      treats it as routine feedback or deflects to generic policy/documentation.
      A reply that opens with "Thank you for your feedback" (not "complaint") and
      closes with "please refer to our terms and conditions" in response to a
      complaint intent is a dismissal pattern — flag this even if the specific
      grievance details are absent from the state.
    - Policy violation: the reply GRANTS or commits to an action that the sub-agent
      findings explicitly require owner approval for.
      NOT a policy violation: a reply that explicitly defers ("would need to go
      through management review before we could commit to anything") or routes
      ("I'll forward your request for review") — that is correct handling.

  The rule-based scanner produces known false positives. Downgrade to "low" when
  the flag matches one of these four patterns:

    1. Confidence false positive — confidence_level=medium triggered the flag,
       but the reply makes no factual claims at all (pure acknowledgement or
       deferral). There is nothing to be uncertain about; the flag is moot.
       Example: "We'll look into this and get back to you with an update."
       → DOWNGRADE TO LOW.

    2. Tone false positive — an over-apologetic tone flag was triggered, but the
       reply contains no fault admission, liability language, or specific
       commitment. Empathy phrasing ("I'm sorry you had to experience this
       inconvenience", "we appreciate your patience") is not a fault admission.
       "Sorry you experienced X" ≠ "we caused X".
       → DOWNGRADE TO LOW.

    3. Policy-approval false positive — a POLICY REQUIRES APPROVAL flag was
       raised, but the reply explicitly declines to commit to the
       approval-required action (e.g. "extended returns are outside what we can
       offer directly", "I'm unable to commit to anything at this stage"). The
       reply handles the policy correctly; the flag is moot.
       IMPORTANT: Even if the reply mentions that exceptions exist or could be
       reviewed by management, if the reply makes NO affirmative commitment to
       grant the approval-required action, the flag is still a false positive.
       "Our management team reviews exceptions on a case-by-case basis" alone
       is NOT a commitment — it describes a process, not a promise.
       → DOWNGRADE TO LOW whenever the reply contains explicit refusal or
         non-commitment language AND makes no affirmative grant of the action.

    4. Complaint-intent false positive — intent_label=complaint triggered the
       flag, but the reply is generic routing with no specific grievance
       engagement, no commitments, and no fault language (e.g. "We take all
       feedback seriously and will pass your comments to the relevant team for
       review"). NOTE: a reply that substantively acknowledges the complaint
       (e.g. "We've logged your concern and our team will review it carefully")
       is NOT a false positive — keep that at medium.
       KEY TEST: Does the reply reference this SPECIFIC concern, or does it use
       boilerplate that could apply to ANY message? Phrases like "We take all
       feedback seriously" and "pass your comments to the relevant team" are
       generic boilerplate (→ low). Phrases like "We've logged your concern" or
       "will review it carefully" reference the specific case (→ medium).
       → DOWNGRADE TO LOW only for the generic boilerplate routing case.

  Maintain "medium" only when the reply contains genuine risk content that does
  not meet the 'high' threshold and does not match any of the four false positive
  patterns above.
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
