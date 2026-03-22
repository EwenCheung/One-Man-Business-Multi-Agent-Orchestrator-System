"""
Update Agent (Section 7.10)

Post-send memory updates — summarises the interaction,
selectively stores durable preferences and action items.
"""


def update_agent(state: dict) -> dict:
    """
    Decide what to persist after the interaction.

    Reads from state:
        - raw_message
        - reply_text
        - risk_level

    Writes to state:
        - memory_updates
    """
    # TODO: Summarise interaction, decide what to store, prepare digest
    raise NotImplementedError("Update agent not yet implemented")
