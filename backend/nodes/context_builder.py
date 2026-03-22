"""
Context Builder Node (Section 7.3)

Pure logic — assembles initial context from DB and cache
before the orchestrator plans. No LLM needed.
"""


def context_builder_node(state: dict) -> dict:
    """
    Gather initial context for the orchestrator.

    Reads from state:
        - sender_id
        - predicted_role
        - thread_id

    Writes to state:
        - context  (recent history, relationship metadata, tone defaults)
    """
    # TODO: Fetch recent history, relationship metadata, tone defaults from DB/cache
    raise NotImplementedError("Context builder node not yet implemented")
