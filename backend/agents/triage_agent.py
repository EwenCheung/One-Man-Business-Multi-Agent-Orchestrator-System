"""
Triage Agent (Section 7.2)

Classifies incoming messages: intent, sender role, urgency.
Uses an LLM to perform lightweight classification.

Add your LangChain chain / prompt here.
"""

# TODO: from langchain_openai import ChatOpenAI
# TODO: from langchain_core.prompts import ChatPromptTemplate


def triage_agent(state: dict) -> dict:
    """
    Analyse the message and classify intent, role, urgency.

    Reads from state:
        - raw_message
        - sender_id

    Writes to state:
        - predicted_role
        - intent_label
        - urgency_level
        - needs_internal_retrieval
        - needs_external_research
        - risk_hint
    """
    # TODO: Build prompt, call LLM, parse structured output
    raise NotImplementedError("Triage agent not yet implemented")
