"""
Reply Agent (PROPOSAL §4.6)

Drafts the final candidate response using completed task results
and role-appropriate tone constraints from SOUL.md and RULE.md.

## TODO
- [ ] Build LLM prompt that injects: SOUL.md (tone), RULE.md (constraints), completed task results
- [ ] Apply role-specific tone rules:
      - Customer:  polite, professional, helpful, retention-focused
      - Supplier:  direct, firm, negotiate, maximize profit
      - Investor:  promote, optimistic, ROI-focused
      - Partner:   professional, mutual-benefit, strategic
      - Employee:  motivate, clear expectations, constructive
      - Government: compliant, exact, formal
- [ ] Use structured output: reply_text + confidence_note
- [ ] Surface uncertainty safely — do NOT hide gaps in knowledge
- [ ] Enforce: use ONLY facts from completed_tasks, never invent
- [ ] Add try/except with structured failure return
"""

from __future__ import annotations

import logging

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from backend.config import settings
from backend.graph.state import PipelineState, SubTask

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


_TONE_INSTRUCTIONS = {
    "customer": """\
Tone: Polite, professional, and genuinely helpful.
- Prioritise the customer's satisfaction and clarity.
- Resolve complaints swiftly and take ownership where appropriate.
- Explain things in plain language — avoid jargon.""",

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
Tone: Motivating, clear, and constructively authoritative.
- Provide clear expectations and actionable direction.
- Offer constructive feedback with empathy — not criticism.
- Acknowledge good work; address issues directly but fairly.
- Foster a sense of ownership and team culture.""",
}

_DEFAULT_TONE = """\
Tone: Professional and clear.
- Communicate directly and helpfully.
- Do not over-promise or speculate beyond confirmed information."""


_REPLY_PROMPT = """\
You are drafting a reply on behalf of the business founder. Every word
must be grounded in your SOUL identity, the RULE hard constraints, and the
verified sub-agent findings below — nothing else.

══════════════════════════════════════════════════════════════════
SOUL — Your Identity & Voice
══════════════════════════════════════════════════════════════════
{soul_context}

Voice & Tone Guidelines:
- Use active voice.
- Be polite but do not apologise excessively unless a clear failure occurred on our end.
- When you do not know the answer, do not guess. State that you will verify the information or request that the sender wait while you fetch it.
- You are representing a human founder. Do not introduce yourself as an AI unless explicitly required by compliance.

══════════════════════════════════════════════════════════════════
RULE — Hard Constraints (NEVER violate these)
══════════════════════════════════════════════════════════════════
{rules_context}

══════════════════════════════════════════════════════════════════
ROLE-SPECIFIC TONE
══════════════════════════════════════════════════════════════════
The sender is a {sender_role}. Apply this tone precisely:

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
        lines.append(
            f"Task {t['task_id']} [{t['assignee'].upper()}]: {t['description']}\n"
            f"Result:\n{t['result']}"
        )
    return "\n\n──────────────────────────────\n\n".join(lines)


def _format_short_term_memory(history: list[dict]) -> str:
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
    for entry in history[-8:]:   # Cap at last 8 turns to stay within context
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


def reply_agent(state: PipelineState) -> dict:
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
    role            = state.get("sender_role", "unknown")
    sender_name     = state.get("sender_name", "there")
    intent_label    = state.get("intent_label", "unknown")
    urgency_level   = state.get("urgency_level", "normal")
    raw_message     = state.get("raw_message", "")
    completed_tasks = state.get("completed_tasks", [])
    soul_context    = state.get("soul_context", "")
    rules_context   = state.get("rules_context", "")
    long_term_mem   = state.get("long_term_memory", "No long-term memory available.")
    short_term_mem  = state.get("short_term_memory", [])

    logger.info(
        "ReplyAgent: drafting reply | role=%s intent=%s urgency=%s tasks=%d",
        role, intent_label, urgency_level, len(completed_tasks),
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
        short_term_memory=_format_short_term_memory(short_term_mem),
        raw_message=raw_message,
        completed_tasks_text=_format_completed_tasks(completed_tasks),
    )

    llm = ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0.3,
    )
    reply_llm = llm.with_structured_output(ReplyOutput)

    try:
        output = reply_llm.invoke(formatted_prompt)
        logger.info("ReplyAgent: reply drafted successfully for role=%s", role)
        return {
            "reply_text":      output.reply_text,
            "confidence_note": output.confidence_note,
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
        }
