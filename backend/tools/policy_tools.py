"""
Policy Retrieval Tools

Two-stage retrieval pipeline for the policy agent:

  Stage 1 — search_policy_chunks
    Embeds the query and runs a pgvector cosine similarity search against
    policy_chunks, returning the top-K most similar chunks.

  Stage 2 — rerank_chunks
    Passes the top-K candidates and the original query to a local
    cross-encoder (mixedbread-ai/mxbai-rerank-base-v1).  Each (query, chunk)
    pair is scored directly, then chunks are sorted by score and the top-N
    are returned.  This corrects cases where embedding similarity retrieves
    topically close but contextually less useful chunks.
"""

from langchain_openai import OpenAIEmbeddings
from sentence_transformers import CrossEncoder
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.models import PolicyChunk


# ─── Stage 2 model — loaded once at import time ───────────────────────────────

def _load_reranker() -> CrossEncoder:
    if settings.HF_TOKEN:
        from huggingface_hub import login
        login(token=settings.HF_TOKEN)
    return CrossEncoder(settings.RERANKER_MODEL)

_reranker = _load_reranker()


# ─── Stage 1: Semantic search ─────────────────────────────────────────────────

def search_policy_chunks(
    session: Session,
    query: str,
    top_k: int | None = None,
    category: str | None = None,
) -> list[dict]:
    """
    Embed the query and retrieve the top-K most similar PolicyChunk rows using
    pgvector cosine distance.

    Args:
        session:  SQLAlchemy session.
        query:    Natural language policy question.
        top_k:    Number of candidates to retrieve (defaults to settings.POLICY_TOP_K).
        category: Optional filter — restrict results to a single policy category
                  (e.g. "returns", "pricing").

    Returns:
        List of chunk dicts sorted by cosine similarity (highest first).
        Fields: chunk_id, chunk_text, source_file, page_number, category,
                hard_constraint, similarity_score.
    """
    k = top_k or settings.POLICY_TOP_K

    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )
    query_vector = embedder.embed_query(query)

    distance_expr = PolicyChunk.embedding.cosine_distance(query_vector)
    q = (
        session.query(PolicyChunk, distance_expr.label("distance"))
        .order_by(distance_expr)
        .limit(k)
    )
    if category:
        q = q.filter(PolicyChunk.category == category)

    results = []
    for chunk, distance in q.all():
        results.append({
            "chunk_id": chunk.id,
            "chunk_text": chunk.chunk_text,
            "source_file": chunk.source_file,
            "page_number": chunk.page_number,
            "subheading": chunk.subheading,
            "category": chunk.category,
            "hard_constraint": chunk.hard_constraint,
            "similarity_score": round(1.0 - distance, 4),
        })
    return results


# ─── Stage 2: Cross-encoder reranker ─────────────────────────────────────────

def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_n: int | None = None,
) -> list[dict]:
    """
    Rerank retrieved chunks using a local cross-encoder model.

    Each (query, chunk_text) pair is scored directly by the model.  Chunks are
    then sorted by score descending and the top-N are returned.

    Args:
        query:   The original natural language policy question.
        chunks:  Candidates from search_policy_chunks (top-K list).
        top_n:   How many chunks to keep after reranking (defaults to settings.POLICY_TOP_N).

    Returns:
        The top-N chunks from the input list, reordered by cross-encoder score.
        Falls through to the original list unchanged if it is already within top_n.
    """
    n = top_n or settings.POLICY_TOP_N

    if not chunks:
        return []

    if len(chunks) <= n:
        return chunks

    pairs = [(query, c["chunk_text"]) for c in chunks]
    scores = _reranker.predict(pairs)

    ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked[:n]]
