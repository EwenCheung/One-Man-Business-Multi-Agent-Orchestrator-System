"""
Policy Ingestion Pipeline

Converts every PDF policies to Markdown, splits the Markdown into
structure-aware chunks, embeds each chunk with OpenAI, and stores the results as
PolicyChunk rows in pgvector.

Flow:
    PDF → pymupdf4llm (Markdown) → MarkdownTextSplitter → OpenAIEmbeddings → policy_chunks

Usage:
    uv run python backend/db/ingest_policies.py          
"""

import argparse
from pathlib import Path

import fitz  # PyMuPDF 
import pymupdf4llm
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownTextSplitter
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.policies.generate_policies import POLICY_SPECS
from backend.db.models import PolicyChunk

# ─── Constants ───────────────────────────────────────────────────────────────

POLICIES_DIR = Path(__file__).parent.parent / "policies"

# filename → {category, hard_constraint} — sourced from the generator spec list
_SPEC_BY_FILE: dict[str, dict] = {s["filename"]: s for s in POLICY_SPECS}


# ─── PDF → Markdown conversion ───────────────────────────────────────────────

def _pdf_to_markdown_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """
    Convert each page of a PDF to Markdown using pymupdf4llm.

    pymupdf4llm preserves document structure — headings, bold text, and tables
    are carried through as Markdown syntax, which produces cleaner chunk
    boundaries than raw text extraction.

    Returns [(page_number, markdown_text), ...] for every non-empty page.
    """
    doc = fitz.open(str(pdf_path))
    pages = []
    for i in range(len(doc)):
        md = pymupdf4llm.to_markdown(doc, pages=[i]).strip()
        if md:
            pages.append((i + 1, md))  # 1-indexed page numbers
    return pages


# ─── Chunking ────────────────────────────────────────────────────────────────

def _chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    """
    Split each page's Markdown into overlapping chunks using MarkdownTextSplitter.

    MarkdownTextSplitter respects heading boundaries (##, ###) before falling
    back to paragraph and sentence splits, so chunks naturally align with policy
    sections rather than cutting across them mid-sentence.
    """
    splitter = MarkdownTextSplitter(
        chunk_size=settings.POLICY_CHUNK_SIZE,
        chunk_overlap=settings.POLICY_CHUNK_OVERLAP,
    )
    chunks = []
    for page_number, md_text in pages:
        for idx, split in enumerate(splitter.split_text(md_text)):
            chunks.append({
                "page_number": page_number,
                "chunk_index": idx,
                "chunk_text": split,
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
        2. Convert PDF pages to Markdown via pymupdf4llm.
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
