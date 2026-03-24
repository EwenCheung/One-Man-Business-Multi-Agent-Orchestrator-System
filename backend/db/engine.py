'''
Sets up SQLalchemy for relational DB
'''

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings

# Create SQLalchemy engine and session
engine = create_engine(settings.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

# Create base class for ORM models
class Base(DeclarativeBase):
    pass
# Create session generator
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()