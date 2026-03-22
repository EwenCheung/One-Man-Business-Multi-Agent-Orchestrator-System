"""
Reply Agent (Section 7.7)

Drafts the final candidate response using the completed tasks
and role-appropriate tone constraints.
"""

from backend.graph.state import PipelineState


def reply_agent(state: PipelineState) -> dict:
    """
    Generate a final reply adapting the tone to the target role.

    Tone Rules:
    - Customer : polite, professional, and helpful
    - Supplier : bargain, professional, convince, clean, direct, firm, maximise my profit
    - Investor : promote, selling, engage, optimistic
    - Partner  : bargain, professional, optimistic, maximise my profit
    - Owner    : full responsibility, partner, provide suggestions
    """
    role = state.get("sender_role", "unknown")
    completed_tasks = state.get("completed_tasks", [])
    soul = state.get("soul_context", "")
    rules = state.get("rules_context", "")
    
    # TODO: Build role-aware prompt incorporating soul and rules, format tone instructions, call LLM
    
    return {
        "reply_text": f"(Stub) Tone-applied reply drafted for role: {role}.",
        "confidence_note": "Stub Confidence"
    }
