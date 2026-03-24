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

from backend.graph.state import PipelineState

# ────────────────────────────────────────────────────────
# Prompt — generates the final reply with tone control
# ────────────────────────────────────────────────────────
REPLY_SYSTEM_PROMPT = """\
You are the Reply Agent. Your job is to draft a professional response
on behalf of the business owner.

### Identity & Voice
{soul_context}

### Business Rules & Constraints
{rules_context}

### Role-Specific Tone
The sender is a **{sender_role}**. Adapt your tone accordingly:
- Customer:  Polite, professional, helpful. Prioritize retention.
- Supplier:  Direct, firm, professional. Negotiate to maximize our profit.
- Investor:  Promotional, confident, data-driven. Focus on growth and ROI.
- Partner:   Collaborative, strategic, mutual-benefit. Build long-term trust.
- Employee:  Motivating, clear, constructive. Set expectations.
- Government: Formal, compliant, exact. Demonstrate contribution.

### Gathered Information
The following facts were collected by our research team:
{completed_tasks_summary}

### Original Message
From: {sender_name}
Message: {raw_message}

### Instructions
- Draft a reply using ONLY the gathered information above.
- If information is incomplete, acknowledge what you don't know rather than guessing.
- Keep the response concise and actionable.
- Do NOT make promises, price commitments, or guarantees unless the policy agent confirmed it.
"""


def reply_agent(state: PipelineState) -> dict:
    """
    Generate a final reply with role-appropriate tone.

    Input:  Full PipelineState
    Output: dict with reply_text and confidence_note

    Functions needed (implement later):
    - _format_completed_tasks(tasks) -> str    # Summarize all completed task results
    - _build_reply_prompt(state) -> str        # Assemble full prompt from state
    - _call_llm(prompt) -> str                 # LLM call with structured output
    - _assess_confidence(reply, tasks) -> str   # Rate confidence in the reply
    """
    # TODO: Replace stub with real LLM-powered reply generation
    role = state.get("sender_role", "unknown")
    return {
        "reply_text": f"(Stub) Tone-applied reply drafted for role: {role}.",
        "confidence_note": "Stub Confidence"
    }
