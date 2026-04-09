"""
Supabase client singleton for Auth operations.

Usage:
    from backend.services.supabase_client import get_supabase_client

    supabase = get_supabase_client()
    if supabase:
        user = supabase.auth.admin.create_user(...)
"""

from supabase import create_client, Client
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

_supabase_client: Client | None = None


def get_supabase_client() -> Client | None:
    """
    Returns a singleton Supabase client instance.
    Returns None if credentials are not configured.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not configured. "
            "Supabase Auth operations will be skipped."
        )
        return None

    try:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        logger.info("Supabase client initialized successfully")
        return _supabase_client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None
