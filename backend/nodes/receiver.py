"""
Receiver Node (Section 7.1)

Pure logic — standardizes raw incoming messages into the
internal format. No LLM needed.
"""


def receiver_node(state: dict) -> dict:
    """
    Convert raw input into a standardized message.

    Reads from state:
        - raw_message
        - sender_id

    Writes to state:
        - sender_role  (looked up from DB, or "unknown")
        - source_type
    """
    # TODO: Look up sender in contacts DB, attach known metadata
    raise NotImplementedError("Receiver node not yet implemented")
