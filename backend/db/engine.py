"""
Unified SQLAlchemy engine — Supabase PostgreSQL only.

All agents, nodes, and services use `SessionLocal` from this module.

Engine and session factory are created lazily on first use so that importing
this module (e.g. in tests or static analysis) does not raise an error when
SUPABASE_DB_URL is not configured.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings

# Lazy singletons — not created at import time.
_engine = None
_session_factory = None


def _build_engine():
    if not settings.SUPABASE_DB_URL:
        raise RuntimeError(
            "SUPABASE_DB_URL is not configured. "
            "Set it in your .env file to point to your Supabase PostgreSQL instance."
        )
    return create_engine(
        settings.SUPABASE_DB_URL,
        connect_args={"sslmode": "require"},
        echo=False,
        pool_pre_ping=True,
    )


def _init_db():
    global _engine, _session_factory
    if _session_factory is None:
        _engine = _build_engine()
        _session_factory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


class _LazySessionLocal:
    """Callable that creates DB sessions on first call, deferring engine validation to first use."""

    def __call__(self) -> Session:
        _init_db()
        assert _session_factory is not None
        return _session_factory()


SessionLocal = _LazySessionLocal()


def get_session():
    """Dependency generator for unified DB sessions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def __getattr__(name: str):
    """Lazy module attribute accessor — defers engine creation to first access.

    Supported lazy attributes:
      - ``engine``: the SQLAlchemy Engine singleton

    Allows ``from backend.db.engine import engine`` (used by admin scripts such
    as ``init_db.py``) without raising at import time.
    """
    if name == "engine":
        _init_db()
        return _engine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")