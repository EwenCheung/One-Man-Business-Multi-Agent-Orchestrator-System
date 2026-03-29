"""
Sets up SQLAlchemy for relational DBs
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.config import settings

# Existing DB
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Supabase Postgres
if settings.SUPABASE_DB_URL:
    supabase_engine = create_engine(
        settings.SUPABASE_DB_URL,
        connect_args={"sslmode": "require"},
        echo=False,
    )
    SupabaseSessionLocal = sessionmaker(
        bind=supabase_engine,
        autocommit=False,
        autoflush=False,
    )
else:
    supabase_engine = None
    SupabaseSessionLocal = None

def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_supabase_session():
    session = SupabaseSessionLocal()
    try:
        yield session
    finally:
        session.close()