"""
External Research Sub-Agent (Section 7.6)

Performs bounded external search if internal retrieval is insufficient.
Accepts a specific SubTask assigned by the Orchestrator.
"""

from backend.graph.state import SubTask


def research_agent(task: SubTask) -> dict:
    """
    Execute external web search or competitor lookup.

    Input state: SubTask
    Returns: dict with 'completed_tasks' list to merge back to main state.
    """
    # TODO: Call web search API / summarize findings
    
    completed_task = task.copy()
    completed_task["status"] = "completed"
    completed_task["result"] = f"(Stub) External research complete for: {task['description']}"

    return {"completed_tasks": [completed_task]}
