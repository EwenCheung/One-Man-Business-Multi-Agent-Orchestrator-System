"""
Langfuse Tracing Integration

Initializes the Langfuse CallbackHandler for LangGraph observability.
"""

import logging
from langfuse.langchain import CallbackHandler
from backend.config import settings

logger = logging.getLogger(__name__)

def get_langfuse_handler() -> CallbackHandler | None:
    """
    Returns a configured Langfuse CallbackHandler if credentials are set.
    Otherwise returns None (graceful degradation).
    """
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.debug("Langfuse tracing disabled: missing credentials.")
        return None

    try:
        handler = CallbackHandler()
        logger.info("Langfuse tracing enabled.")
        return handler
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse tracing: {e}")
        return None
