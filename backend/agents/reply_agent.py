"""
Reply Agent

Drafts the final candidate response using completed sub-agent task results
and role-appropriate tone constraints from SOUL.md and RULE.md.

## Behaviour
- Injects SOUL.md (persona/voice), RULE.md (hard constraints), and all
  completed sub-agent results into a structured LLM prompt.
- Applies role-specific tone posture (customer, supplier, investor, partner,
  owner) on top of universal voice guidelines.
- Returns a ``ReplyOutput`` structured object via LangChain's
  ``with_structured_output`` containing:
    - ``reply_text``       — the final, ready-to-send reply.
    - ``confidence_note``  — internal 1-2 sentence confidence summary.
    - ``confidence_level`` — machine-readable ``"high"`` | ``"medium"`` | ``"low"``.
    - ``unverified_claims``— list of hedged statements not confirmed by sub-agents.
    - ``tone_flags``       — list of detected tone anomalies
                             (``"over-apologetic"``, ``"over-committed"``,
                              ``"defensive"``, ``"speculative"``).
- Surfaces uncertainty explicitly — never invents facts absent from
  ``completed_tasks``.
- Falls back to a safe acknowledgement reply on LLM failure, setting
  ``confidence_level`` to ``"low"`` so the risk node can gate it accordingly.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from backend.graph.state import PipelineState, SubTask
from backend.utils.llm_provider import get_chat_llm

logger = logging.getLogger(__name__)


class ReplyOutput(BaseModel):
    """Typed output from the Reply Agent LLM call."""

    reply_text: str = Field(
        description=(
            "The final, ready-to-send reply. Must fully embody the SOUL persona "
            "and respect all RULE constraints. No meta-commentary or placeholders."
        )
    )
    confidence_note: str = Field(
        description=(
            "A brief internal note (1-2 sentences) for the Orchestrator explaining "
            "the confidence level and any caveats. Examples: "
            "'High confidence — pricing confirmed by policy agent.' "
            "'Medium confidence — stock not explicitly confirmed; reply hedged accordingly.'"
        )
    )
    confidence_level: str = Field(
        description=(
            "Machine-readable confidence summary. Must be exactly one of: "
            "'high' — all claims in the reply are confirmed by sub-agent results; "
            "'medium' — some claims are hedged or not fully confirmed; "
            "'low' — significant gaps exist; reply relies on follow-up commitments."
        )
    )
    unverified_claims: list[str] = Field(
        default_factory=list,
        description=(
            "List of specific statements in the reply that could not be fully confirmed "
            "by sub-agent results. Each entry is a short phrase identifying the claim. "
            "Examples: ['ships within 3 days — not confirmed by retriever', "
            "'price quoted — not verified by policy agent']. Empty if all claims verified."
        ),
    )
    tone_flags: list[str] = Field(
        default_factory=list,
        description=(
            "List of tone anomalies detected in the drafted reply that may signal risk. "
            "Use only these labels where applicable: "
            "'over-apologetic' — excessive apologies that imply liability; "
            "'over-committed' — promises made beyond what was verified; "
            "'defensive' — tone that may escalate rather than de-escalate; "
            "'speculative' — forward-looking statements not grounded in confirmed data. "
            "Empty list if no anomalies detected."
        ),
    )


_TONE_INSTRUCTIONS = {
    "customer": """\
Tone: Polite, professional, and genuinely helpful.
- Prioritise the customer's satisfaction and clarity.
- Resolve complaints swiftly and take ownership where appropriate.
- Explain things in plain language — avoid jargon.
- For price objections, negotiate using verified bundle, quantity, stock, and policy guidance before escalating.
- Never reveal raw cost, internal margin, or internal approval thresholds to the customer.""",
    "supplier": """\
Tone: Firm, direct, and professionally confident.
- Negotiate to maximise our profit margin and secure the best supply terms.
- Be respectful but never desperate or apologetic about our position.
- Use volume commitments and contract terms as leverage where appropriate.""",
    "investor": """\
Tone: Promotional, optimistic, and engaging.
- Lead with our strongest ROI and growth metrics.
- Frame every data point as evidence of momentum and future potential.
- Project confidence in the business trajectory.
- Invite further engagement: calls, detailed reports, next steps.""",
    "partner": """\
Tone: Professional, optimistic, and commercially minded.
- Frame the conversation as a mutually beneficial collaboration.
- Protect our profit share and operational boundaries firmly but warmly.
- Reference existing agreement terms when relevant.""",
    "owner": """\
Tone: Strategic, proactive, and analytical (acting as the Owner's AI Business Partner).
- You are speaking DIRECTLY TO THE OWNER of the business.
- Act as an active business partner, giving proactive insights, information, and updates.
- Do NOT act like a passive assistant that only gives the exact outcome asked.
- Anticipate the owner's needs: if they ask about sales, provide the sales data PLUS insights on margins or low stock.
- Never hold back internal data, costs, or margins from the owner.""",
}

_DEFAULT_TONE = """\
Tone: Professional and clear.
- Communicate directly and helpfully.
- Do not over-promise or speculate beyond confirmed information."""


_REPLY_PROMPT = """\
If the Sender Role is 'owner', you are acting as the AI Business Partner speaking DIRECTLY to the business owner.
Otherwise, you are drafting a reply on behalf of the business founder to a third party.
Every word must be grounded in your SOUL identity, the RULE hard constraints, and the
verified sub-agent findings below — nothing else.

══════════════════════════════════════════════════════════════════
SOUL — Your Identity & Voice
══════════════════════════════════════════════════════════════════
{soul_context}

══════════════════════════════════════════════════════════════════
RULE — Hard Constraints (NEVER violate these)
══════════════════════════════════════════════════════════════════
{rules_context}

══════════════════════════════════════════════════════════════════
VOICE & TONE
══════════════════════════════════════════════════════════════════
Universal (apply to every reply regardless of role):
- Use active voice. Be direct and concise.
- Be polite but do not apologise excessively unless a clear failure occurred on our end.
- When you do not know the answer, do not guess. Commit to verifying and following up.
- You are representing a human founder. Do not introduce yourself as an AI unless explicitly required by compliance.
- For discount and bundle requests, use verified internal negotiation guidance first; escalate only if the requested terms exceed the approved range.
- Never disclose cost price, internal margin, or internal negotiation limits directly.
- For list-heavy database answers, show only the 5 to 10 most relevant items by default unless the user explicitly asks for all items.
- If the user asks for more after a prior list response, continue with additional unseen items from the verified data instead of repeating the first batch.
- When you intentionally show only part of a longer list, end with a concise line such as: "Let me know if you'd like more."

The relationship of the sender to the owner is {sender_role}. Layer this posture on top of the universal guidelines:
{tone_instructions}

══════════════════════════════════════════════════════════════════
CONVERSATION CONTEXT
══════════════════════════════════════════════════════════════════
Sender Name   : {sender_name}
Sender Role   : {sender_role}
Intent        : {intent_label}
Urgency       : {urgency_level}

Long-Term Memory (preferences, history):
{long_term_memory}

Recent Conversation History:
{short_term_memory}

Sender Memory Summary:
{sender_memory}

══════════════════════════════════════════════════════════════════
ORIGINAL MESSAGE
══════════════════════════════════════════════════════════════════
{raw_message}

══════════════════════════════════════════════════════════════════
VERIFIED INFORMATION FROM SUB-AGENTS
══════════════════════════════════════════════════════════════════
Only the following has been confirmed. Do NOT invent facts, prices, dates, or
figures absent from this section. If the sender's question requires information
not listed here, commit to following up rather than guessing.

{completed_tasks_text}

══════════════════════════════════════════════════════════════════
TASK
══════════════════════════════════════════════════════════════════
Before writing, briefly consider:
• What is the sender's core ask or concern?
• Which verified findings directly address it?
• Are there gaps that require a follow-up commitment?

Negotiation rule:
- If verified internal negotiation guidance says approval_required=false, present the verified offer directly and do NOT ask for owner approval.
- If verified internal negotiation guidance says approval_required=true, do NOT promise the requested concession; state that it requires review.
- When negotiation guidance provides a customer-safe summary, prefer it over improvising your own pricing logic.

Then draft the reply. Close with a concrete next step or clear call to action.
"""


def _format_completed_tasks(tasks: list[SubTask]) -> str:
    """Render completed sub-agent tasks as a numbered, readable text block.

    Args:
        tasks: List of completed ``SubTask`` dicts from ``PipelineState``.

    Returns:
        A multi-line string with one labelled block per task, or a fallback
        message if the list is empty.
    """
    if not tasks:
        return "No sub-agent results available."
    lines = []
    for t in tasks:
        if t.get("internal_only"):
            lines.append(
                f"Task {t['task_id']} [INTERNAL ANALYSIS]: {t['description']}\n"
                f"Result:\n{t.get('public_summary', 'Internal analysis completed; sensitive details redacted.')}"
            )
            continue
        lines.append(
            f"Task {t['task_id']} [{t['assignee'].upper()}]: {t['description']}\n"
            f"Result:\n{t['result']}"
        )
    return "\n\n──────────────────────────────\n\n".join(lines)


def _format_short_term_memory(history: list[dict[str, str]]) -> str:
    """Render recent message history as a readable transcript.

    Args:
        history: List of message dicts from ``PipelineState.short_term_memory``.

    Returns:
        A newline-separated transcript string, or a fallback message if the
        history list is empty.
    """
    if not history:
        return "No recent conversation history."
    lines = []
    for entry in history[-8:]:  # Cap at last 8 turns to stay within context
        role = entry.get("role", "unknown").capitalize()
        content = entry.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _get_tone_instructions(sender_role: str) -> str:
    """Return tone instructions for the given sender role (case-insensitive).

    Args:
        sender_role: The sender's role string from ``PipelineState.sender_role``
            (e.g. ``"customer"``, ``"supplier"``, ``"investor"``).

    Returns:
        A multi-line tone instruction string ready to be injected directly
        into the reply prompt.
    """
    return _TONE_INSTRUCTIONS.get(sender_role.lower().strip(), _DEFAULT_TONE)


def reply_agent(state: PipelineState) -> dict[str, object]:
    """
    Generate a final, role-aware, SOUL-grounded reply. Reads all completed sub-agent
    task results from the state and produces a single ready-to-send reply.

    Args:
        state: The full ``PipelineState`` at the point of reply generation.
            Expected keys used by this function:
            - ``sender_role``     (str): Role of the message sender.
            - ``sender_name``     (str): Display name of the sender.
            - ``intent_label``    (str): Classified intent of the message.
            - ``urgency_level``   (str): Urgency classification.
            - ``raw_message``     (str): Original incoming message text.
            - ``completed_tasks`` (list[SubTask]): Results from all sub-agents.
            - ``soul_context``    (str): Loaded content of SOUL.md.
            - ``rules_context``   (str): Loaded content of RULE.md.
            - ``long_term_memory``(str): Long-term memory summary.
            - ``short_term_memory``(list[dict]): Recent conversation history.

    Returns:
        A dict with two keys that LangGraph merges into ``PipelineState``:
        - ``"reply_text"``      (str): The final, ready-to-send reply.
        - ``"confidence_note"`` (str): Internal confidence note for the
          Orchestrator describing what was and was not verified.
    """
    role = state.get("sender_role", "unknown")
    sender_name = state.get("sender_name", "there")
    intent_label = state.get("intent_label", "unknown")
    urgency_level = state.get("urgency_level", "normal")
    raw_message = state.get("raw_message", "")
    completed_tasks = state.get("completed_tasks", [])
    soul_context = state.get("soul_context", "")
    rules_context = state.get("rules_context", "")
    long_term_mem = state.get("long_term_memory", "No long-term memory available.")
    sender_memory = state.get("sender_memory", "No sender memory summary available yet.")
    short_term_mem = state.get("short_term_memory", [])

    logger.info(
        "ReplyAgent: drafting reply | role=%s intent=%s urgency=%s tasks=%d",
        role,
        intent_label,
        urgency_level,
        len(completed_tasks),
    )

    prompt = PromptTemplate.from_template(_REPLY_PROMPT)
    formatted_prompt = prompt.format(
        soul_context=soul_context or "(SOUL not loaded — use professional, confident tone)",
        rules_context=rules_context or "(RULE not loaded — apply conservative defaults)",
        sender_role=role,
        sender_name=sender_name,
        intent_label=intent_label,
        urgency_level=urgency_level,
        tone_instructions=_get_tone_instructions(role),
        long_term_memory=long_term_mem,
        sender_memory=sender_memory,
        short_term_memory=_format_short_term_memory(short_term_mem),
        raw_message=raw_message,
        completed_tasks_text=_format_completed_tasks(completed_tasks),
    )

    llm = get_chat_llm(temperature=0.3)
    reply_llm = llm.with_structured_output(ReplyOutput)

    try:
        output_raw = reply_llm.invoke(formatted_prompt)
        if isinstance(output_raw, ReplyOutput):
            output = output_raw
        elif isinstance(output_raw, dict):
            output = ReplyOutput.model_validate(output_raw)
        else:
            output = ReplyOutput.model_validate(cast(Any, output_raw).model_dump())
        logger.info("ReplyAgent: reply drafted successfully for role=%s", role)
        return {
            "reply_text": output.reply_text,
            "confidence_note": output.confidence_note,
            "confidence_level": output.confidence_level,
            "unverified_claims": output.unverified_claims,
            "tone_flags": output.tone_flags,
        }
    except Exception as exc:
        logger.error("ReplyAgent: LLM call failed — %s", exc)
        return {
            "reply_text": (
                f"Thank you for your message{', ' + sender_name if sender_name != 'there' else ''}. "
                "I need a moment to verify some details before I can give you a complete answer. "
                "I will follow up with you shortly."
            ),
            "confidence_note": f"Reply Agent LLM call failed: {exc}. Fallback acknowledgement sent.",
            "confidence_level": "low",
            "unverified_claims": [],
            "tone_flags": [],
        }
