"""
Pipeline Guards — Safety & Constraint Verification

Provides validation functions to protect the orchestrator from runaway
execution costs, infinite loops, and overloading sub-agents.

CIRCUIT BREAKERS (Claude Code v2.1.88 patterns):
- Task budget enforcement: Hard stop when token budget exceeded
- Permission denial tracking: Audit log for all rejected tool invocations
"""

import logging
from typing import Any, Callable
from backend.config import settings
from backend.graph.state import PipelineState, SubTask

logger = logging.getLogger(__name__)

_TASK_BUDGET_TOKEN_LIMIT = 500000
_permission_denials: list[dict[str, Any]] = []


def check_replan_limit(
    state: PipelineState, max_cycles: int = settings.MAX_REPLAN_CYCLES
) -> tuple[bool, str | None]:
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
        logger.warning(
            "Parallel task limit exceeded: requested %d, truncating to %d", len(tasks), max_tasks
        )
        return tasks[:max_tasks]
    return tasks


def check_task_budget(
    current_token_count: int, max_tokens: int = _TASK_BUDGET_TOKEN_LIMIT
) -> tuple[bool, str | None]:
    """
    Task budget circuit breaker. Halts orchestration if token usage exceeds limit.

    Args:
        current_token_count: Cumulative token count for current orchestration session
        max_tokens: Maximum allowed tokens (default 500K)

    Returns:
        (is_exceeded, error_message) tuple
    """
    if current_token_count >= max_tokens:
        msg = f"Task budget exceeded: {current_token_count} >= {max_tokens} tokens. Halting orchestration."
        logger.error(msg)
        return True, msg
    return False, None


def track_permission_denial(
    tool_name: str, sender_role: str, reason: str, context: dict[str, Any] | None = None
) -> None:
    """
    Record permission denial for audit purposes. Thread-safe append to module-level list.

    Args:
        tool_name: Name of the tool that was denied access
        sender_role: Role of the requester
        reason: Explanation of why access was denied
        context: Additional context dict (e.g., task_id, timestamp)
    """
    denial_record = {
        "tool_name": tool_name,
        "sender_role": sender_role,
        "reason": reason,
        "context": context or {},
    }
    _permission_denials.append(denial_record)
    logger.warning(
        "Permission denial recorded: tool=%s role=%s reason=%s", tool_name, sender_role, reason
    )


def get_permission_denials() -> list[dict[str, Any]]:
    """Retrieve all permission denial records for audit review."""
    return _permission_denials.copy()


def reset_permission_denials() -> None:
    """Clear permission denial records. Call at start of new orchestration session."""
    global _permission_denials
    _permission_denials = []


def wrap_tool_with_permission_check(
    tool_fn: Callable, allowed_roles: set[str], tool_name: str
) -> Callable:
    """
    Wrap a tool function with role-based permission checking and denial tracking.

    Args:
        tool_fn: Original tool function
        allowed_roles: Set of roles permitted to use this tool
        tool_name: Name of the tool for logging

    Returns:
        Wrapped function that enforces permissions
    """

    def wrapped(*args, sender_role: str = "unknown", **kwargs):
        if sender_role not in allowed_roles:
            track_permission_denial(
                tool_name=tool_name,
                sender_role=sender_role,
                reason=f"Role '{sender_role}' not in allowed roles: {allowed_roles}",
                context={"args": str(args)[:200], "kwargs": str(kwargs)[:200]},
            )
            raise PermissionError(
                f"Access denied: {tool_name} not available for role '{sender_role}'"
            )
        return tool_fn(*args, **kwargs)

    return wrapped
