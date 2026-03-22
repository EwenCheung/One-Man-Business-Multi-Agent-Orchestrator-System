"""
Orchestrator Agent (Section 7.4)

Core planner — decides which agents to invoke, in what order,
and what data sources are allowed based on role & policy.

This is the central LangGraph routing logic.
"""


def orchestrator_agent(state: dict) -> dict:
    """
    Build a response plan and decide routing.

    Reads from state:
        - raw_message
        - predicted_role
        - context
        - policy_constraints

    Writes to state:
        - plan_steps
        - requires_external_research
        - requires_approval
    """
    # TODO: Use LLM to reason about which steps are needed
    raise NotImplementedError("Orchestrator agent not yet implemented")
