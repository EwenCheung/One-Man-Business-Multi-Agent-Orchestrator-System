"""
Policy & Constraint Sub-Agent (Section 7.8)

Looks up company policies regarding pricing, compliance, etc.
Accepts a specific SubTask assigned by the Orchestrator.
"""

from backend.graph.state import SubTask


def policy_agent(task: SubTask) -> dict:
    """
    Execute the specific policy lookup instructions.

    Input state: SubTask
    Returns: dict with 'completed_tasks' list to merge back to main state.
    """
    # TODO: Query policy_rules table or vector store
    
    completed_task = task.copy()
    completed_task["status"] = "completed"
    completed_task["result"] = f"(Stub) Policy rules found for: {task['description']}"

    return {"completed_tasks": [completed_task]}
