"""
Context Compression — Context Window Management

Summarizes completed tasks and histories to prevent blowing up the LLM
context window during deep replanning loops.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

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
    """
    if not completed_tasks:
        return "None yet."

    # First pass: try formatting the tasks cleanly
    task_lines = []
    for t in completed_tasks:
        try:
            resp = json.loads(t["result"])
            # Extract just the critical bits for the orchestrator
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
        
    full_text = "\n\n".join(task_lines)
    
    # Check token count
    token_count = _estimate_tokens(full_text)
    if token_count <= max_tokens:
        return full_text
        
    logger.warning("Context compression triggered: %d > %d tokens", token_count, max_tokens)
    
    # Second pass: aggressive truncation
    compressed_lines = []
    for t in completed_tasks:
        try:
            resp = json.loads(t["result"])
            compressed_lines.append(
                f"[{t.get('assignee')}] resp: {resp.get('status')} | "
                f"facts: {resp.get('facts', [])} | rules: {resp.get('constraints', [])}"
            )
        except Exception:
            compressed_lines.append(f"[{t.get('assignee')}] result snippet: {str(t.get('result', ''))[:200]}...")
            
    return "COMPRESSED TASK SUMMARY:\n" + "\n".join(compressed_lines)
