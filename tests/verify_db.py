from backend.db.engine import engine
from sqlalchemy import inspect

def verify():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Found {len(tables)} tables:")
    for table in tables:
        columns = [col["name"] for col in inspector.get_columns(table)]
        print(f"  {table}: {', '.join(columns)}")

if __name__ == "__main__":
    verify()