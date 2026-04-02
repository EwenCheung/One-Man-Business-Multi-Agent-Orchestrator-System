"""
Context Compression — Context Window Management

Summarizes completed tasks and histories to prevent blowing up the LLM
context window during deep replanning loops.

AUTO-COMPACT CIRCUIT BREAKER (Claude Code v2.1.88 pattern):
- Triggers when context exceeds threshold (13K token buffer from max)
- Stops after 3 consecutive compression failures
- Prevents runaway token growth in orchestration loops
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Circuit breaker state (module-level for simplicity)
_compression_failure_count = 0
_MAX_COMPRESSION_FAILURES = 3
_AUTO_COMPACT_THRESHOLD = 13000  # Claude pattern: 13K buffer before max context


def _estimate_tokens(text: str) -> int:
    """Fallback token estimator if tiktoken is not installed."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return len(text) // 4  # 1 token ~= 4 chars rule of thumb


def compress_context(completed_tasks: list[dict[str, Any]], max_tokens: int = 4000) -> str:
    """
    Takes a list of completed sub-tasks and returns a formatted string.
    If the estimated token count exceeds max_tokens, it applies structural
    compression (summarization/truncation) to fit within limits.

    Circuit breaker: Raises RuntimeError after 3 consecutive compression failures
    to prevent runaway token growth in orchestration loops.
    """
    global _compression_failure_count

    if not completed_tasks:
        _compression_failure_count = 0
        return "None yet."

    full_text = _format_tasks(completed_tasks)
    token_count = _estimate_tokens(full_text)

    if token_count <= max_tokens:
        _compression_failure_count = 0
        return full_text

    logger.warning("Context compression triggered: %d > %d tokens", token_count, max_tokens)

    compressed = _aggressive_truncation(completed_tasks)
    compressed_token_count = _estimate_tokens(compressed)

    if compressed_token_count > max_tokens:
        _compression_failure_count += 1
        logger.error(
            "Compression failed (%d/%d): %d tokens after truncation",
            _compression_failure_count,
            _MAX_COMPRESSION_FAILURES,
            compressed_token_count,
        )

        if _compression_failure_count >= _MAX_COMPRESSION_FAILURES:
            raise RuntimeError(
                f"Circuit breaker triggered: {_MAX_COMPRESSION_FAILURES} consecutive "
                f"compression failures. Token count: {compressed_token_count} > {max_tokens}. "
                "Halting to prevent runaway token growth."
            )
    else:
        _compression_failure_count = 0

    return compressed


def _format_tasks(completed_tasks: list[dict[str, Any]]) -> str:
    task_lines = []
    for t in completed_tasks:
        try:
            resp = json.loads(t["result"])
            status = resp.get("status", "unknown")
            conf = resp.get("confidence", "low")
            result_snippet = resp.get("result", "")
            if len(result_snippet) > 1000:
                result_snippet = result_snippet[:1000] + "... [truncated]"

            display = (
                f"[status: {status} | conf: {conf}]\n"
                f"Result: {result_snippet}\n"
                f"Facts: {resp.get('facts', [])}\n"
                f"Constraints: {resp.get('constraints', [])}"
            )
        except Exception:
            text = str(t.get("result", ""))
            if len(text) > 1000:
                text = text[:1000] + "... [truncated]"
            display = text

        task_lines.append(f"Task {t.get('task_id')} ({t.get('assignee')}):\n{display}")

    return "\n\n".join(task_lines)


def _aggressive_truncation(completed_tasks: list[dict[str, Any]]) -> str:
    compressed_lines = []
    for t in completed_tasks:
        try:
            resp = json.loads(t["result"])
            compressed_lines.append(
                f"[{t.get('assignee')}] resp: {resp.get('status')} | "
                f"facts: {resp.get('facts', [])} | rules: {resp.get('constraints', [])}"
            )
        except Exception:
            compressed_lines.append(
                f"[{t.get('assignee')}] result snippet: {str(t.get('result', ''))[:200]}..."
            )

    return "COMPRESSED TASK SUMMARY:\n" + "\n".join(compressed_lines)


def should_trigger_auto_compact(current_token_count: int, max_context_window: int = 200000) -> bool:
    """
    Check if auto-compact should trigger based on context size.

    Args:
        current_token_count: Current total token usage in orchestration session
        max_context_window: Model's maximum context window (default 200K for Claude)

    Returns:
        True if auto-compact should trigger, False otherwise
    """
    buffer_remaining = max_context_window - current_token_count
    return buffer_remaining <= _AUTO_COMPACT_THRESHOLD


def reset_circuit_breaker():
    """Reset compression failure counter. Call at start of new orchestration session."""
    global _compression_failure_count
    _compression_failure_count = 0
