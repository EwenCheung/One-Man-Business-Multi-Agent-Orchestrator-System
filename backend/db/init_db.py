from backend.db.engine import engine, Base
from backend.db import orm_models

def init():
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("Done.")

if __name__ == "__main__":
    init()