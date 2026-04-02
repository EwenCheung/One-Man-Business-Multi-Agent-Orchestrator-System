"""
Langfuse Tracing Integration

Initializes the Langfuse CallbackHandler for LangGraph observability.
"""

import logging
from langfuse.langchain import CallbackHandler
from backend.config import settings

logger = logging.getLogger(__name__)


def get_langfuse_handler(trace_id: str | None = None) -> CallbackHandler | None:
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.debug("Langfuse tracing disabled: missing credentials.")
        return None

    try:
        handler = CallbackHandler(
            trace_context={"trace_id": trace_id} if trace_id else None,
        )
        logger.info("Langfuse tracing enabled.")
        return handler
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse tracing: {e}")
        return None
