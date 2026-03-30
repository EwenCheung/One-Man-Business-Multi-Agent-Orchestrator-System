"""
Policy Ingestion Pipeline

Converts every PDF policies to Markdown, splits the Markdown into
structure-aware chunks, embeds each chunk with OpenAI, and stores the results as
PolicyChunk rows in pgvector.

Flow:
    PDF → docling (Markdown) → MarkdownTextSplitter → OpenAIEmbeddings → policy_chunks

Usage:
    uv run python backend/db/ingest_policies.py
"""

import argparse
import re
from pathlib import Path

from collections import defaultdict

from docling.document_converter import DocumentConverter
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownTextSplitter
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.policy_metadata import POLICY_SPECS
from backend.db.models import PolicyChunk

# ─── Constants ───────────────────────────────────────────────────────────────

POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"

# filename → {category, hard_constraint} — sourced from the generator spec list
_SPEC_BY_FILE: dict[str, dict] = {s["filename"]: s for s in POLICY_SPECS}


# ─── PDF → Markdown conversion ───────────────────────────────────────────────

def _pdf_to_markdown_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """
    Convert a PDF to Markdown using docling, grouped by page.

    docling preserves document structure — headings, bold text, and tables
    are carried through as Markdown syntax, which produces cleaner chunk
    boundaries than raw text extraction. Elements are grouped by their
    provenance page number so each entry maps to a single physical page.

    Returns [(page_number, markdown_text), ...] for every non-empty page.
    """
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    page_parts: dict[int, list[str]] = defaultdict(list)
    for item, _ in doc.iterate_items():
        prov = getattr(item, "prov", None)
        if not prov:
            continue
        page_no = prov[0].page_no
        text = getattr(item, "text", None)
        if text and text.strip():
            page_parts[page_no].append(text.strip())

    return [
        (page_no, "\n\n".join(parts))
        for page_no, parts in sorted(page_parts.items())
        if parts
    ]


# ─── Chunking ────────────────────────────────────────────────────────────────

def _extract_heading(text: str) -> str | None:
    """Return the heading text if the chunk starts with a Markdown heading, else None."""
    m = re.match(r'^#{1,6}\s+(.+)', text.strip())
    return m.group(1).strip() if m else None


def _chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    """
    Split each page's Markdown into overlapping chunks using MarkdownTextSplitter.

    MarkdownTextSplitter respects heading boundaries (##, ###) before falling
    back to paragraph and sentence splits, so chunks naturally align with policy
    sections rather than cutting across them mid-sentence.

    The current heading is tracked across chunks: a chunk that opens with a
    Markdown heading updates the running heading; otherwise the previous heading
    is carried forward so every chunk knows which section it belongs to.
    """
    splitter = MarkdownTextSplitter(
        chunk_size=settings.POLICY_CHUNK_SIZE,
        chunk_overlap=settings.POLICY_CHUNK_OVERLAP,
    )
    chunks = []
    current_heading: str | None = None
    for page_number, md_text in pages:
        for idx, split in enumerate(splitter.split_text(md_text)):
            heading = _extract_heading(split)
            if heading:
                current_heading = heading
            chunks.append({
                "page_number": page_number,
                "chunk_index": idx,
                "chunk_text": split,
                "subheading": current_heading,
            })
    return chunks


# ─── Ingestion ───────────────────────────────────────────────────────────────

def _ingest_file(
    session: Session,
    pdf_path: Path,
    embedder: OpenAIEmbeddings,
    force: bool,
) -> int:
    """
    Ingest one PDF into policy_chunks.

    Steps:
        1. Check for existing rows — skip or delete depending on --force.
        2. Convert PDF pages to Markdown via docling.
        3. Chunk Markdown using MarkdownTextSplitter.
        4. Embed all chunks in a single batched API call.
        5. Bulk-insert PolicyChunk rows.

    Returns the number of chunks stored (0 if skipped).
    """
    filename = pdf_path.name
    spec = _SPEC_BY_FILE.get(filename, {})
    category = spec.get("category")
    hard_constraint = spec.get("hard_constraint", False)

    existing_count = session.query(PolicyChunk).filter_by(source_file=filename).count()
    if existing_count and not force:
        print(f"  skipping {filename} ({existing_count} chunks in DB — use --force to re-ingest)")
        return 0

    if existing_count and force:
        session.query(PolicyChunk).filter_by(source_file=filename).delete()
        session.flush()

    pages = _pdf_to_markdown_pages(pdf_path)
    if not pages:
        print(f"  warning: {filename} yielded no extractable content — skipping")
        return 0

    chunks = _chunk_pages(pages)
    texts = [c["chunk_text"] for c in chunks]

    # Single batched embedding call — avoids one API round trip per chunk
    vectors = embedder.embed_documents(texts)

    rows = [
        PolicyChunk(
            source_file=filename,
            page_number=c["page_number"],
            chunk_index=c["chunk_index"],
            chunk_text=c["chunk_text"],
            subheading=c["subheading"],
            category=category,
            hard_constraint=hard_constraint,
            embedding=vector,
        )
        for c, vector in zip(chunks, vectors)
    ]
    session.add_all(rows)
    session.commit()
    return len(rows)


# ─── Main pipeline ───────────────────────────────────────────────────────────

def ingest(force: bool = False) -> None:
    pdf_files = sorted(POLICIES_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {POLICIES_DIR}. Run generate_policies.py first.")
        return

    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )

    session: Session = SessionLocal()
    try:
        for pdf_path in pdf_files:
            print(f"  ingesting {pdf_path.name} ...")
            count = _ingest_file(session, pdf_path, embedder, force)
            if count:
                print(f"  stored {count} chunks")
    finally:
        session.close()

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest policy PDFs into pgvector.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing chunks and re-ingest all PDFs.",
    )
    args = parser.parse_args()
    ingest(force=args.force)
