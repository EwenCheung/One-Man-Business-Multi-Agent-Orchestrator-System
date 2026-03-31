"""
Pipeline Guards — Safety & Constraint Verification

Provides validation functions to protect the orchestrator from runaway
execution costs, infinite loops, and overloading sub-agents.
"""

import logging
from backend.config import settings
from backend.graph.state import PipelineState, SubTask

logger = logging.getLogger(__name__)

def check_replan_limit(state: PipelineState, max_cycles: int = settings.MAX_REPLAN_CYCLES) -> tuple[bool, str | None]:
    """
    Check if the orchestrator has exceeded its permitted replanning loops.
    Returns (is_exceeded, warning_message).
    """
    replan_count = state.get("replan_count", 0)
    if replan_count >= max_cycles:
        msg = f"Max replan cycles ({max_cycles}) reached. Forcing route to reply."
        logger.warning(msg)
        return True, msg
    return False, None

def check_parallel_task_limit(tasks: list[SubTask], max_tasks: int = 4) -> list[SubTask]:
    """
    Ensure the orchestrator does not spawn an unbounded number of parallel tasks.
    Truncates the list and logs a warning if the limit is exceeded.
    """
    if len(tasks) > max_tasks:
        logger.warning("Parallel task limit exceeded: requested %d, truncating to %d", len(tasks), max_tasks)
        return tasks[:max_tasks]
    return tasks
