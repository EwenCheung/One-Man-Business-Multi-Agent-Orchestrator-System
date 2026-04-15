"""
Langfuse Tracing Integration

Initializes the Langfuse CallbackHandler for LangGraph observability.
"""

import logging
from langfuse import Langfuse
from langfuse import get_client
from langfuse.langchain import CallbackHandler
from backend.config import settings

logger = logging.getLogger(__name__)


def _langfuse_base_url() -> str:
    return settings.LANGFUSE_BASE_URL or settings.LANGFUSE_HOST or "https://cloud.langfuse.com"


def ensure_langfuse_client() -> Langfuse | None:
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        logger.debug("Langfuse tracing disabled: missing credentials.")
        return None

    try:
        client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            base_url=_langfuse_base_url(),
        )
        logger.debug("Langfuse client initialized.")
        return client
    except Exception as e:
        logger.warning("Failed to initialize Langfuse client: %s", e)
        return None


def get_langfuse_handler(trace_id: str | None = None) -> CallbackHandler | None:
    if ensure_langfuse_client() is None:
        return None

    try:
        handler = CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            trace_context={"trace_id": trace_id} if trace_id else None,
        )
        logger.info("Langfuse tracing enabled.")
        return handler
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse tracing: {e}")
        return None


def flush_langfuse_handler(handler: CallbackHandler | None) -> None:
    if handler is None:
        return

    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        return

    try:
        get_client(public_key=settings.LANGFUSE_PUBLIC_KEY).flush()
    except Exception as e:
        logger.debug("Langfuse flush skipped after failure: %s", e)
