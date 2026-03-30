"""
Policy Retrieval Tools

Two-stage retrieval pipeline for the policy agent:

  Stage 1 — search_policy_chunks
    Embeds the query and runs a pgvector cosine similarity search against
    policy_chunks, returning the top-K most similar chunks.

  Stage 2 — rerank_chunks
    Passes the top-K candidates and the original query to gpt-4o-mini.
    The LLM acts as a lightweight cross-encoder, scoring each chunk for
    contextual relevance and returning the top-N indices in ranked order.
    This corrects cases where embedding similarity retrieves topically close
    but contextually less useful chunks.
"""

from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.models import PolicyChunk
from backend.utils.llm_provider import get_chat_llm


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


# ─── Stage 2: LLM reranker ────────────────────────────────────────────────────

class _RerankResult(BaseModel):
    ranked_indices: list[int]  # indices into the input chunks list, most relevant first


def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_n: int | None = None,
) -> list[dict]:
    """
    Rerank retrieved chunks using another llm as a lightweight cross-encoder.

    The model receives the original query and all candidate chunks with numeric
    labels, then returns the indices of the most relevant ones in ranked order.

    Args:
        query:   The original natural language policy question.
        chunks:  Candidates from search_policy_chunks (top-K list).
        top_n:   How many chunks to keep after reranking (defaults to settings.POLICY_TOP_N).

    Returns:
        The top-N chunks from the input list, reordered by LLM relevance judgement.
        Falls through to the original list unchanged if it is already within top_n.
    """
    n = top_n or settings.POLICY_TOP_N

    if not chunks:
        return []

    if len(chunks) <= n:
        return chunks

    llm = get_chat_llm(scope="policy", temperature=0.0)
    structured_llm = llm.with_structured_output(_RerankResult)

    numbered_chunks = "\n\n".join(
        f"[{i}]\n{c['chunk_text']}" for i, c in enumerate(chunks)
    )

    messages = [
        SystemMessage(content=(
            "You are a relevance ranking assistant for a business policy system. "
            "Given a question and a numbered list of policy document excerpts, "
            "identify which excerpts most directly and completely answer the question. "
            "Return only the indices of the most relevant excerpts, ordered from most "
            "to least relevant. Omit any excerpt that does not help answer the question."
        )),
        HumanMessage(content=(
            f"Question: {query}\n\n"
            f"Policy excerpts:\n{numbered_chunks}\n\n"
            f"Return the {n} most relevant indices in order of relevance."
        )),
    ]

    result: _RerankResult = structured_llm.invoke(messages)
    ranked = result.ranked_indices[:n]
    return [chunks[i] for i in ranked if i < len(chunks)]
