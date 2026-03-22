"""
External Research Agent (Section 7.6)

Optional — only invoked when internal retrieval is insufficient.
Performs bounded external search (web, competitor analysis, etc.).
"""


def research_agent(state: dict) -> dict:
    """
    Search external sources for supplementary information.

    Reads from state:
        - raw_message
        - retrieved_context

    Writes to state:
        - research_findings
    """
    # TODO: Web search API, competitor price lookup, summarise with LLM
    raise NotImplementedError("Research agent not yet implemented")
