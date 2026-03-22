"""
Reply Agent (Section 7.7)

Drafts the candidate response using approved context,
role-appropriate tone, and policy constraints.
"""


def reply_agent(state: dict) -> dict:
    """
    Generate a candidate reply grounded in context and policy.

    Reads from state:
        - raw_message
        - predicted_role
        - retrieved_context
        - research_findings  (optional)
        - policy_constraints
        - disclosure_boundaries

    Writes to state:
        - reply_text
        - confidence_note
    """
    # TODO: Build role-aware prompt, call LLM, generate reply
    raise NotImplementedError("Reply agent not yet implemented")
