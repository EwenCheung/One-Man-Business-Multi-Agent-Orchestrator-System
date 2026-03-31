"""
Unified SQLAlchemy engine — Supabase PostgreSQL only.

All agents, nodes, and services use `SessionLocal` from this module.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.config import settings

if not settings.SUPABASE_DB_URL:
    raise RuntimeError(
        "SUPABASE_DB_URL is not configured. "
        "Set it in your .env file to point to your Supabase PostgreSQL instance."
    )

engine = create_engine(
    settings.SUPABASE_DB_URL,
    connect_args={"sslmode": "require"},
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session():
    """Dependency generator for unified DB sessions."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()