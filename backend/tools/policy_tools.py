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

import logging

from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.models import PolicyChunk

logger = logging.getLogger(__name__)


# ─── Stage 2 model — loaded lazily so lightweight runtimes can skip it ───────

_reranker = None
_reranker_load_attempted = False


def _get_reranker():
    global _reranker, _reranker_load_attempted

    if _reranker_load_attempted:
        return _reranker

    _reranker_load_attempted = True

    try:
        if settings.HF_TOKEN:
            from huggingface_hub import login

            login(token=settings.HF_TOKEN)

        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(settings.RERANKER_MODEL)
    except Exception as exc:
        logger.warning(
            "Policy reranker unavailable; falling back to retrieval ordering: %s",
            exc,
        )
        _reranker = None

    return _reranker


_CATEGORY_HINTS = {
    "returns": ["return", "refund", "replacement", "defective", "warranty"],
    "pricing": ["price", "pricing", "discount", "discounts", "quote", "cost", "margin"],
    "data_privacy": ["privacy", "personal data", "data", "delete", "retention", "confidential"],
    "supplier": ["supplier", "invoice", "payment terms", "lead time", "procurement", "supply"],
    "partner": ["partner", "referral", "commission", "affiliate", "revenue share"],
    "owner_benefit": [
        "owner approval",
        "owner review",
        "owner sign-off",
        "concession",
        "waiver",
        "below cost",
        "negotiation",
        "negotiation parameters",
        "on behalf",
        "binding offer",
        "representation",
        "disclose",
        "guarantee",
    ],
}


def _score_value(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def infer_policy_categories(query: str, sender_role: str | None = None) -> list[str]:
    query_text = (query or "").lower()
    matches = {
        category
        for category, hints in _CATEGORY_HINTS.items()
        if any(hint in query_text for hint in hints)
    }

    role_map = {
        "supplier": "supplier",
        "partner": "partner",
        "investor": "data_privacy",
    }
    role_category = role_map.get((sender_role or "").lower())
    if role_category:
        matches.add(role_category)

    ordered = [
        "owner_benefit",
        "pricing",
        "returns",
        "supplier",
        "partner",
        "data_privacy",
    ]
    return [category for category in ordered if category in matches]


# ─── Stage 1: Semantic search ─────────────────────────────────────────────────


def search_policy_chunks(
    session: Session,
    query: str,
    top_k: int | None = None,
    category: str | None = None,
    categories: list[str] | None = None,
) -> list[dict[str, object]]:
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
        api_key=SecretStr(settings.OPENAI_API_KEY),
    )
    query_vector = embedder.embed_query(query)

    distance_expr = PolicyChunk.embedding.cosine_distance(query_vector)
    q = session.query(PolicyChunk, distance_expr.label("distance"))
    if category:
        q = q.filter(PolicyChunk.category == category)
    elif categories:
        q = q.filter(PolicyChunk.category.in_(categories))
    q = q.order_by(distance_expr).limit(k)

    results = []
    for chunk, distance in q.all():
        results.append(
            {
                "chunk_id": chunk.id,
                "chunk_text": chunk.chunk_text,
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "subheading": chunk.subheading,
                "category": chunk.category,
                "hard_constraint": chunk.hard_constraint,
                "similarity_score": round(1.0 - distance, 4),
                "retrieval_mode": "semantic",
            }
        )
    return results


def search_policy_chunks_lexical(
    session: Session,
    query: str,
    top_k: int | None = None,
    categories: list[str] | None = None,
) -> list[dict[str, object]]:
    k = top_k or settings.POLICY_TOP_K
    terms = [part.strip() for part in query.split() if part.strip()]
    if not terms:
        return []

    filters = []
    score_terms = []
    for term in terms:
        pattern = f"%{term}%"
        filters.append(
            or_(
                PolicyChunk.chunk_text.ilike(pattern),
                PolicyChunk.subheading.ilike(pattern),
                PolicyChunk.source_file.ilike(pattern),
                PolicyChunk.category.ilike(pattern),
            )
        )
        term_score = case(
            (PolicyChunk.chunk_text.ilike(pattern), 3),
            (PolicyChunk.subheading.ilike(pattern), 2),
            (PolicyChunk.category.ilike(pattern), 2),
            (PolicyChunk.source_file.ilike(pattern), 1),
            else_=0,
        )
        score_terms.append(term_score)

    score = score_terms[0]
    for term_score in score_terms[1:]:
        score = score + term_score

    query_builder = session.query(PolicyChunk, score.label("lexical_score")).filter(or_(*filters))
    if categories:
        query_builder = query_builder.filter(PolicyChunk.category.in_(categories))

    rows = query_builder.order_by(score.desc()).limit(k).all()
    results = []
    for chunk, lexical_score in rows:
        results.append(
            {
                "chunk_id": chunk.id,
                "chunk_text": chunk.chunk_text,
                "source_file": chunk.source_file,
                "page_number": chunk.page_number,
                "subheading": chunk.subheading,
                "category": chunk.category,
                "hard_constraint": chunk.hard_constraint,
                "similarity_score": float(lexical_score or 0),
                "retrieval_mode": "lexical",
            }
        )
    return results


def merge_policy_candidates(*candidate_groups: list[dict[str, object]]) -> list[dict[str, object]]:
    merged: dict[object, dict[str, object]] = {}
    for group in candidate_groups:
        for candidate in group:
            key = candidate["chunk_id"]
            existing = merged.get(key)
            candidate_score = _score_value(candidate.get("similarity_score", 0))
            existing_score = _score_value(existing.get("similarity_score", 0)) if existing else 0.0
            if not existing or candidate_score > existing_score:
                merged[key] = dict(candidate)
            elif existing and candidate.get("retrieval_mode"):
                candidate_mode = str(candidate.get("retrieval_mode", ""))
                existing_mode = str(existing.get("retrieval_mode", ""))
                if candidate_mode and candidate_mode not in existing_mode:
                    existing["retrieval_mode"] = f"{existing_mode or 'semantic'}+{candidate_mode}"
    return sorted(
        merged.values(),
        key=lambda item: _score_value(item.get("similarity_score", 0)),
        reverse=True,
    )


# ─── Stage 2: Cross-encoder reranker ─────────────────────────────────────────


def rerank_chunks(
    query: str,
    chunks: list[dict[str, object]],
    top_n: int | None = None,
) -> list[dict[str, object]]:
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

    reranker = _get_reranker()
    if reranker is None:
        return chunks[:n]

    pairs = [(query, str(c["chunk_text"])) for c in chunks]
    scores = reranker.predict(pairs)

    ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked[:n]]
