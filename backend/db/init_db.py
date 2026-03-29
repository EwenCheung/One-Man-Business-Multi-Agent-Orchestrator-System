from sqlalchemy import text

from backend.db.engine import engine
from backend.db.models import Base
from backend.db import models  # noqa: F401 — registers ORM models with Base.metadata

def init():
    # Enable vector db
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Done.")

if __name__ == "__main__":
    init()