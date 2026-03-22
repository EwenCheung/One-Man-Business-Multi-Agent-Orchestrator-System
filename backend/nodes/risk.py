"""
Risk Node (Section 7.9)

Rule-based — aggregates risk signals and decides whether
the reply can be sent or must be held for owner approval.
No LLM needed.
"""


def risk_node(state: dict) -> dict:
    """
    Evaluate risk and decide approval requirements.

    Reads from state:
        - reply_text
        - risk_hint
        - policy_constraints
        - disclosure_boundaries

    Writes to state:
        - risk_level       ("low" | "medium" | "high")
        - requires_approval
        - risk_flags
    """
    # TODO: Check for disclosure violations, sensitive commitments, etc.
    raise NotImplementedError("Risk node not yet implemented")
