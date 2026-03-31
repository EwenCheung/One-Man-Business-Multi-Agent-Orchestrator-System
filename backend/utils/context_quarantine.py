"""
Context Quarantine — Safe Error Handling

Contains logic to encapsulate raw agent failures, stripping out internal details
(e.g., stack traces, underlying APIs) before they reach the orchestrator or reply agent.
"""

import logging
import traceback
from typing import Any

from backend.models.agent_response import AgentResponse

logger = logging.getLogger(__name__)

def sanitize_output(error_msg: str) -> str:
    """
    Strips raw stack traces and internal references from an error message
    so it is safe to show to the LLM or user.
    """
    if "Traceback" in error_msg:
        # Keep only the last line (the actual Exception message)
        lines = error_msg.strip().split("\n")
        return f"Internal execution failure: {lines[-1]}"
    return str(error_msg)

def quarantine_result(task_id: str, assignee: str, exc: Exception) -> dict[str, Any]:
    """
    Wraps an exception in a standardised 'failed' SubTask payload.
    Uses the AgentResponse contract to ensure consistency.
    """
    raw_error = str(exc)
    if not raw_error:
        raw_error = traceback.format_exc()
        
    sanitized = sanitize_output(raw_error)
    logger.error("Task %s (%s) quarantined due to: %s", task_id, assignee, sanitized)
    
    resp = AgentResponse(
        status="failed",
        confidence="low",
        result=f"Agent '{assignee}' failed during execution: {sanitized}",
        unknowns=["execution_failure"],
        constraints=[]
    )
    
    return {
        "task_id": task_id,
        "assignee": assignee,
        "status": "failed",
        "description": "Quarantined due to internal error.",
        "result": resp.model_dump_json()
    }
