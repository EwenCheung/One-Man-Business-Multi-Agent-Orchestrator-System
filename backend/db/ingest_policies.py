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
import uuid
from pathlib import Path
from typing import Any

from collections import defaultdict

from docling.document_converter import DocumentConverter
from pydantic import SecretStr
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownTextSplitter
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import PolicyChunk

# ─── Constants ───────────────────────────────────────────────────────────────

POLICIES_DIR = Path(__file__).parent.parent / "data" / "policies"
_SIDECAR_PATH = POLICIES_DIR / "policies_metadata.json"
OWNER_ID = uuid.UUID("4c116430-f683-4a8a-91f7-546fa8bc5d76")

# Suffixes stripped right-to-left to derive a category from a filename.
# e.g. partner_agreement_policy.pdf → partner_agreement → partner
_STRIP_SUFFIXES = ("_policy", "_terms", "_agreement")


def _derive_category(filename: str) -> str:
    stem = Path(filename).stem
    for suffix in _STRIP_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def _load_sidecar() -> dict[str, dict[str, Any]]:
    """
    Load optional per-file metadata overrides from policies_metadata.json.

    The file lives alongside the PDFs in data/policies/ and is keyed by
    filename.  Supported fields: category (str), hard_constraint (bool).

    Example:
        {
            "returns_policy.pdf":      { "hard_constraint": true },
            "pricing_policy.pdf":      { "hard_constraint": true },
            "data_privacy_policy.pdf": { "hard_constraint": true }
        }
    """
    if not _SIDECAR_PATH.exists():
        return {}
    import json

    with open(_SIDECAR_PATH) as f:
        return json.load(f)


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

    return [(page_no, "\n\n".join(parts)) for page_no, parts in sorted(page_parts.items()) if parts]


# ─── Chunking ────────────────────────────────────────────────────────────────


def _extract_heading(text: str) -> str | None:
    """Return the heading text if the chunk starts with a Markdown heading, else None."""
    m = re.match(r"^#{1,6}\s+(.+)", text.strip())
    return m.group(1).strip() if m else None


def _chunk_pages(pages: list[tuple[int, str]]) -> list[dict[str, Any]]:
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
            chunks.append(
                {
                    "page_number": page_number,
                    "chunk_index": idx,
                    "chunk_text": split,
                    "subheading": current_heading,
                }
            )
    return chunks


# ─── Ingestion ───────────────────────────────────────────────────────────────


def _ingest_file(
    session: Session,
    pdf_path: Path,
    embedder: OpenAIEmbeddings,
    force: bool,
    sidecar: dict[str, dict[str, Any]],
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
    overrides = sidecar.get(filename, {})
    category = overrides.get("category") or _derive_category(filename)
    hard_constraint = overrides.get("hard_constraint", True)

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
            owner_id=OWNER_ID,
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

    sidecar = _load_sidecar()
    if sidecar:
        print(f"Loaded metadata overrides for {len(sidecar)} file(s) from policies_metadata.json.")

    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
    )

    session: Session = SessionLocal()
    try:
        if force:
            expected_files = {pdf_path.name for pdf_path in pdf_files}
            session.query(PolicyChunk).filter(~PolicyChunk.source_file.in_(expected_files)).delete(
                synchronize_session=False
            )
            session.commit()
        for pdf_path in pdf_files:
            print(f"  ingesting {pdf_path.name} ...")
            count = _ingest_file(session, pdf_path, embedder, force, sidecar)
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
