"""
Seed Data Loader

Reads CSV files from backend/data/seed/ and loads them into the database
via SQLAlchemy ORM. Insertion order respects foreign key constraints.
Idempotent: skips any table that already has rows.

Usage:
    uv run python backend/db/load_seed_data.py
    uv run python backend/db/load_seed_data.py --with-embeddings
"""

import concurrent.futures
import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric
from sqlalchemy.dialects.postgresql import ARRAY as PGArray, JSONB as JSONBType, UUID as UUIDType
import uuid
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.engine import SessionLocal

SEED_DIR = Path(__file__).parent.parent / "data" / "seed"

_MODEL_MAP = {
    "products.csv": models.Product,
    "customers.csv": models.Customer,
    "suppliers.csv": models.Supplier,
    "partners.csv": models.Partner,
    "orders.csv": models.Order,
    "supply_contracts.csv": models.SupplierProduct,
    "partner_agreements.csv": models.PartnerAgreement,
    "partner_products.csv": models.PartnerProductRelation,
    "external_identities.csv": models.ExternalIdentity,
    "conversation_threads.csv": models.ConversationThread,
    "messages.csv": models.Message,
    "memory_update_proposals.csv": models.MemoryUpdateProposal,
    "held_replies.csv": models.HeldReply,
    "reply_review_records.csv": models.ReplyReviewRecord,
    "pending_approvals.csv": models.PendingApproval,
}

# Insertion order respects foreign key constraints
_LOAD_ORDER = [
    "products.csv",
    "customers.csv",
    "suppliers.csv",
    "partners.csv",
    "orders.csv",
    "supply_contracts.csv",
    "partner_agreements.csv",
    "partner_products.csv",
    "external_identities.csv",
    "conversation_threads.csv",
    "messages.csv",
    "memory_update_proposals.csv",
    "held_replies.csv",
    "reply_review_records.csv",
    "pending_approvals.csv",
]


def _coerce_row(row: dict[str, str], model: Any) -> dict[str, Any]:
    """Cast CSV string values to the correct Python types for each column."""
    col_types = {c.key: c.type for c in model.__table__.columns}
    cleaned = {}
    for k, v in row.items():
        if k not in col_types:
            continue
        if v == "":
            cleaned[k] = None
            continue
        col_type = col_types[k]
        if isinstance(col_type, Integer):
            cleaned[k] = int(v)
        elif isinstance(col_type, Numeric):
            cleaned[k] = Decimal(v)
        elif isinstance(col_type, Boolean):
            cleaned[k] = v.lower() in ("true", "1", "yes")
        elif isinstance(col_type, Date):
            cleaned[k] = date.fromisoformat(v)
        elif isinstance(col_type, DateTime):
            cleaned[k] = datetime.fromisoformat(v.replace("Z", "+00:00"))
        elif isinstance(col_type, UUIDType):
            cleaned[k] = uuid.UUID(v) if v else None
        elif isinstance(col_type, JSONBType):
            cleaned[k] = json.loads(v)
        elif isinstance(col_type, PGArray):
            parsed = json.loads(v)
            cleaned[k] = parsed if isinstance(parsed, list) else [str(parsed)]
        else:
            cleaned[k] = v
    return cleaned


def _embed_concurrently() -> None:
    from backend.db.ingest_business_data import embed

    _EMBEDDABLE_TABLES = ["products", "supply_contracts", "partner_agreements"]
    print("Embedding description columns...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(_EMBEDDABLE_TABLES)) as executor:
        futures = {executor.submit(embed, table=t): t for t in _EMBEDDABLE_TABLES}
        for future in concurrent.futures.as_completed(futures):
            future.result()  # re-raise any exception from a worker thread


def load_all(with_embeddings: bool = False) -> None:
    session: Session = SessionLocal()
    try:
        for filename in _LOAD_ORDER:
            model = _MODEL_MAP[filename]

            if session.query(model).first() is not None:
                print(f"  skipping {model.__tablename__} (already has data)")
                continue

            filepath = SEED_DIR / filename
            if not filepath.exists():
                print(f"  skipping {filename} (not found — run generate_seed_data.py first)")
                continue

            with open(filepath, newline="") as f:
                rows = [model(**_coerce_row(row, model)) for row in csv.DictReader(f)]

            session.add_all(rows)
            session.flush()
            print(f"  loaded {len(rows)} rows → {model.__tablename__}")

        session.commit()
        print("Seed data loaded.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    if with_embeddings:
        _embed_concurrently()

    print("Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Load CSV seed data into the database.")
    parser.add_argument(
        "--with-embeddings",
        action="store_true",
        help="Embed description columns concurrently after loading (requires OpenAI API key).",
    )
    args = parser.parse_args()
    load_all(with_embeddings=args.with_embeddings)
