"""
Error Handler (PROPOSAL §7)

Centralized error handling for agent and tool failures.

## TODO
- [ ] Wrap agent calls with try/except to catch all failure types
- [ ] Classify errors: tool_failure | logic_failure | policy_failure | memory_failure
- [ ] Return structured failure dict (never raise raw exceptions to orchestrator)
- [ ] Retry logic for tool_failure (bounded, with backoff)
- [ ] No retry for logic_failure without changing inputs
- [ ] Log all errors with request context
"""


import traceback
from functools import wraps
from typing import Callable, Any

def classify_error(error: Exception) -> str:
    """
    Classifies an exception into one of:
    - tool_failure (API timeout, DB error, network issue)
    - logic_failure (invalid output, schema violation, bad routing)
    - policy_failure (rule violation, access denied)
    - memory_failure (no data, conflicting data, stale data)
    """
    error_str = str(error).lower()
    if "timeout" in error_str or "connection" in error_str:
        return "tool_failure"
    if "access denied" in error_str or "unauthorized" in error_str:
        return "policy_failure"
    return "logic_failure"


def safe_agent_call(agent_fn: Callable) -> Callable:
    """
    Wraps any agent function call with error handling.
    On failure, returns a structured error result instead of crashing LangGraph.
    
    This fulfills Harness Engineering: Parent components must quarantine 
    child component failures.
    """
    @wraps(agent_fn)
    def wrapper(task: dict) -> dict:
        try:
            return agent_fn(task)
        except Exception as e:
            error_class = classify_error(e)
            error_details = f"[{error_class}]: {str(e)}\n{traceback.format_exc()}"
            
            failed_task = task.copy()
            failed_task["status"] = "failed"
            failed_task["result"] = f"Agent Crash Guard: {error_details}"
            
            # Send the catastrophic failure back to the array the Orchestrator watches
            return {"failed_tasks": [failed_task]}
            
    return wrapper
