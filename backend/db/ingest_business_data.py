"""
Business Data Embedding Pipeline

Generates and stores pgvector embeddings for free-text description columns
on business tables.

Tables and text sources:
    products            → description_embedding  ← "{name}: {description}"
    supply_contracts    → notes_embedding         ← notes
    partner_agreements  → description_embedding  ← "{description} {notes}" (concatenated)

Rows with NULL text fields are skipped — there is nothing to embed.
Rows that already have an embedding are skipped unless --force is used.

Usage:
    uv run python backend/db/ingest_business_data.py
    uv run python backend/db/ingest_business_data.py --force
    uv run python backend/db/ingest_business_data.py --table products
"""

import argparse

from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import PartnerAgreement, Product, SupplierProduct

_BATCH_SIZE = 100  # rows per embedding API call


# ─── Text composers ───────────────────────────────────────────────────────────


def _product_text(row: Product) -> str | None:
    """Embed name + description together so the vector captures what the product is."""
    if not row.description:
        return None
    return f"{row.name}: {row.description}"


def _contract_text(row: SupplierProduct) -> str | None:
    return row.notes or None


def _agreement_text(row: PartnerAgreement) -> str | None:
    parts = [row.description or "", row.notes or ""]
    combined = " ".join(p for p in parts if p).strip()
    return combined or None


# ─── Per-table embedding logic ────────────────────────────────────────────────


def _embed_products(session: Session, embedder: OpenAIEmbeddings, force: bool) -> int:
    q = session.query(Product).filter(Product.description.isnot(None))
    if not force:
        q = q.filter(Product.description_embedding.is_(None))

    rows = q.all()
    if not rows:
        return 0

    texts = [_product_text(r) for r in rows]
    # Some rows may have a non-null description column but yield no usable text
    # after composition — filter those out together with their rows.
    pairs = [(r, t) for r, t in zip(rows, texts) if t]
    if not pairs:
        return 0

    filtered_rows, filtered_texts = zip(*pairs)
    vectors = _batch_embed(embedder, list(filtered_texts))

    for row, vector in zip(filtered_rows, vectors):
        row.description_embedding = vector

    session.commit()
    return len(filtered_rows)


def _embed_supply_contracts(session: Session, embedder: OpenAIEmbeddings, force: bool) -> int:
    q = session.query(SupplierProduct).filter(SupplierProduct.notes.isnot(None))
    if not force:
        q = q.filter(SupplierProduct.notes_embedding.is_(None))

    rows = q.all()
    if not rows:
        return 0

    pairs = [(r, _contract_text(r)) for r in rows]
    pairs = [(r, t) for r, t in pairs if t]
    if not pairs:
        return 0

    filtered_rows, filtered_texts = zip(*pairs)
    vectors = _batch_embed(embedder, list(filtered_texts))

    for row, vector in zip(filtered_rows, vectors):
        row.notes_embedding = vector

    session.commit()
    return len(filtered_rows)


def _embed_partner_agreements(session: Session, embedder: OpenAIEmbeddings, force: bool) -> int:
    q = session.query(PartnerAgreement)
    if not force:
        q = q.filter(PartnerAgreement.description_embedding.is_(None))

    rows = q.all()
    if not rows:
        return 0

    pairs = [(r, _agreement_text(r)) for r in rows]
    pairs = [(r, t) for r, t in pairs if t]
    if not pairs:
        return 0

    filtered_rows, filtered_texts = zip(*pairs)
    vectors = _batch_embed(embedder, list(filtered_texts))

    for row, vector in zip(filtered_rows, vectors):
        row.description_embedding = vector

    session.commit()
    return len(filtered_rows)


# ─── Batched embedding helper ─────────────────────────────────────────────────


def _batch_embed(embedder: OpenAIEmbeddings, texts: list[str]) -> list[list[float]]:
    """Embed texts in fixed-size batches to stay within API rate limits."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        vectors.extend(embedder.embed_documents(batch))
    return vectors


# ─── Main pipeline ────────────────────────────────────────────────────────────

_TABLE_HANDLERS = {
    "products": _embed_products,
    "supply_contracts": _embed_supply_contracts,
    "partner_agreements": _embed_partner_agreements,
}


def embed(force: bool = False, table: str | None = None) -> None:
    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    tables_to_run = {table: _TABLE_HANDLERS[table]} if table else _TABLE_HANDLERS

    session: Session = SessionLocal()
    try:
        for name, handler in tables_to_run.items():
            print(f"  embedding {name} ...")
            count = handler(session, embedder, force)
            if count:
                print(f"  embedded {count} rows")
            else:
                print(
                    f"  nothing to embed (all rows already have embeddings — use --force to re-embed)"
                )
    finally:
        session.close()

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Embed business data description columns into pgvector."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed rows that already have an embedding.",
    )
    parser.add_argument(
        "--table",
        choices=list(_TABLE_HANDLERS.keys()),
        default=None,
        help="Embed only one table (default: all).",
    )
    args = parser.parse_args()
    embed(force=args.force, table=args.table)
