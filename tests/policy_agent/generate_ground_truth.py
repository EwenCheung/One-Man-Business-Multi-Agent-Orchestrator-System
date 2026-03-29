"""
Ground Truth Dataset Generator for Policy Agent RAG Evaluation

Generates a labelled set of (query, relevant_chunk_ids, expected_verdict) triples
by presenting real PolicyChunk content to GPT-4o and asking it to create test
queries grounded in what it reads.  No retrieval system is used in generation —
ground truth is derived purely from the source policy text

Output: tests/policy_agent/ground_truth_dataset.json

Structure per entry:
    query_id              — unique identifier (gt-001, gt-002, …)
    query                 — natural language policy question
    sender_role           — customer | supplier | partner | staff
    relevant_chunk_ids    — list of PolicyChunk.id values that answer this query
                            (null for the 9 manually-specified existing test cases
                            where only verdict accuracy is being benchmarked)
    expected_verdict      — allowed | disallowed | requires_approval | not_covered
    expected_hard_constraint — bool
    category              — policy domain (or "out_of_domain")
    query_type            — factual | edge_case | hard_constraint | requires_approval
                            | out_of_domain | role_variant
    notes                 — brief rationale from the generator

Usage:
    uv run python tests/policy_agent/generate_ground_truth.py
    uv run python tests/policy_agent/generate_ground_truth.py --force   # overwrite

Prerequisites:
    1. PostgreSQL + pgvector running (docker compose up -d db)
    2. policy_chunks table populated (uv run python backend/db/ingest_policies.py)
    3. OPENAI_API_KEY set in .env
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import PolicyChunk

# ─── Paths ───────────────────────────────────────────────────────────────────

OUTPUT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# ─── Generation targets per policy category ──────────────────────────────────
# Tweak counts here to change dataset size without touching logic.

CATEGORY_TARGETS: dict[str, int] = {
    "returns":      7,
    "pricing":      9,
    "data_privacy": 7,
    "supplier":     7,
    "partner":      7,
}

OUT_OF_DOMAIN_COUNT = 5

# ─── Pydantic schemas for structured LLM output ──────────────────────────────

class _GeneratedQuery(BaseModel):
    query: str
    sender_role: str           # customer | supplier | partner | staff
    relevant_chunk_ids: list[int]
    expected_verdict: str      # allowed | disallowed | requires_approval | not_covered
    expected_hard_constraint: bool
    query_type: str            # factual | edge_case | hard_constraint | requires_approval | role_variant
    notes: str


class _PolicyDocumentQueries(BaseModel):
    queries: list[_GeneratedQuery]


class _OutOfDomainQuery(BaseModel):
    query: str
    sender_role: str
    notes: str


class _OutOfDomainQueries(BaseModel):
    queries: list[_OutOfDomainQuery]


# ─── System prompt ───────────────────────────────────────────────────────────

_GENERATION_SYSTEM = """\
You are a QA engineer building an evaluation dataset for a business policy RAG system.
Your task is to generate realistic test queries grounded in the policy excerpts provided.

For each query you generate:
- Base it on content that actually appears in the excerpts — do not invent rules.
- Reference the chunk IDs that contain the relevant text in relevant_chunk_ids.
- Choose sender_role based on who would realistically ask this question.
- Set expected_verdict to the answer the policy actually gives:
    - "allowed"            — the policy explicitly permits the action
    - "disallowed"         — the policy explicitly prohibits it
    - "requires_approval"  — the policy requires owner sign-off before proceeding
    - "not_covered"        — the policy documents shown do not address this at all
- Set expected_hard_constraint=true only if the relevant chunk text states a
  non-overridable rule (check the hard_constraint flag shown per chunk).
- Vary query_type across: factual, edge_case, hard_constraint, requires_approval, role_variant.
- Avoid duplicating very similar queries.

Return valid JSON matching the provided schema exactly.
"""


# ─── Per-document query generation ───────────────────────────────────────────

def _format_chunks_for_prompt(chunks: list[PolicyChunk]) -> str:
    """Render chunks with their DB IDs so the LLM can reference them."""
    parts = []
    for chunk in chunks:
        parts.append(
            f"[chunk_id={chunk.id} | page={chunk.page_number} "
            f"| hard_constraint={chunk.hard_constraint}]\n{chunk.chunk_text}"
        )
    return "\n\n---\n\n".join(parts)


def _generate_for_category(
    llm: ChatOpenAI,
    category: str,
    chunks: list[PolicyChunk],
    n: int,
) -> list[_GeneratedQuery]:
    """Ask the LLM to produce n test queries grounded in the given chunks."""
    chunk_text = _format_chunks_for_prompt(chunks)
    structured_llm = llm.with_structured_output(_PolicyDocumentQueries)

    messages = [
        SystemMessage(content=_GENERATION_SYSTEM),
        HumanMessage(content=(
            f"Policy category: {category}\n\n"
            f"Policy excerpts:\n{chunk_text}\n\n"
            f"Generate exactly {n} test queries for this policy category. "
            f"Include a spread of query_type values: factual, edge_case, "
            f"hard_constraint, requires_approval, role_variant. "
            f"Each query must reference at least one chunk_id from the excerpts above."
        )),
    ]

    result: _PolicyDocumentQueries = structured_llm.invoke(messages)
    return result.queries[:n]  # cap in case LLM returns more


# ─── Out-of-domain query generation ──────────────────────────────────────────

def _generate_out_of_domain(llm: ChatOpenAI, n: int) -> list[_OutOfDomainQuery]:
    """
    Generate n queries that fall outside all policy domains.

    These are used to benchmark not_covered detection rate — the system should
    return verdict=not_covered for all of them.
    """
    structured_llm = llm.with_structured_output(_OutOfDomainQueries)
    covered_domains = ", ".join(CATEGORY_TARGETS.keys())

    messages = [
        SystemMessage(content=(
            "You are a QA engineer building an evaluation dataset. Generate test queries "
            "for a business policy system that covers only these domains: "
            f"{covered_domains}. "
            "Your task is to write queries that are plausible business questions but "
            "fall entirely outside these domains — the system should return 'not_covered' "
            "for every query you generate. Make the queries realistic (not obviously absurd)."
        )),
        HumanMessage(content=(
            f"Generate exactly {n} out-of-domain queries. "
            f"Use a mix of sender_role values: customer, supplier, partner, staff."
        )),
    ]

    result: _OutOfDomainQueries = structured_llm.invoke(messages)
    return result.queries[:n]


# ─── Existing manual test cases ───────────────────────────────────────────────
# These 9 cases from test_policy_agent.py are included as-is.
# relevant_chunk_ids is null — we only evaluate verdict accuracy for these.

_MANUAL_CASES = [
    {
        "query": "How many days do I have to return a product, and what condition must it be in?",
        "sender_role": "customer",
        "relevant_chunk_ids": None,
        "expected_verdict": "allowed",
        "expected_hard_constraint": True,
        "category": "returns",
        "query_type": "factual",
        "notes": "Direct return window + condition question; answer is in policy.",
    },
    {
        "query": "Can I apply both a volume discount and a loyalty discount on the same order?",
        "sender_role": "customer",
        "relevant_chunk_ids": None,
        "expected_verdict": "disallowed",
        "expected_hard_constraint": True,
        "category": "pricing",
        "query_type": "hard_constraint",
        "notes": "Discount stacking is explicitly prohibited.",
    },
    {
        "query": "What personal data do you collect and store about me as a customer?",
        "sender_role": "customer",
        "relevant_chunk_ids": None,
        "expected_verdict": "allowed",
        "expected_hard_constraint": True,
        "category": "data_privacy",
        "query_type": "factual",
        "notes": "Informational — policy lists collected data categories.",
    },
    {
        "query": "What are the standard payment terms for supplier invoices?",
        "sender_role": "supplier",
        "relevant_chunk_ids": None,
        "expected_verdict": "allowed",
        "expected_hard_constraint": False,
        "category": "supplier",
        "query_type": "factual",
        "notes": "Net 30 days payment terms.",
    },
    {
        "query": "What percentage commission do I receive for referrals and when is it paid?",
        "sender_role": "partner",
        "relevant_chunk_ids": None,
        "expected_verdict": "allowed",
        "expected_hard_constraint": False,
        "category": "partner",
        "query_type": "factual",
        "notes": "10% net order value, paid monthly in arrears.",
    },
    {
        "query": (
            "A customer is pushing back hard. Can I offer a discount below cost price "
            "to close the deal, even without owner approval?"
        ),
        "sender_role": "customer",
        "relevant_chunk_ids": None,
        "expected_verdict": "disallowed",
        "expected_hard_constraint": True,
        "category": "pricing",
        "query_type": "hard_constraint",
        "notes": "Below-cost discount without approval violates hard constraint.",
    },
    {
        "query": (
            "I want to offer a 20% discount to a new bulk customer. "
            "Is this allowed, or do I need approval?"
        ),
        "sender_role": "customer",
        "relevant_chunk_ids": None,
        "expected_verdict": "requires_approval",
        "expected_hard_constraint": True,
        "category": "pricing",
        "query_type": "requires_approval",
        "notes": "20% exceeds standard tier — requires owner sign-off.",
    },
    {
        "query": "What is the company's policy on providing employee gym memberships?",
        "sender_role": "customer",
        "relevant_chunk_ids": None,
        "expected_verdict": "not_covered",
        "expected_hard_constraint": False,
        "category": "out_of_domain",
        "query_type": "out_of_domain",
        "notes": "Employee benefits are outside all policy domains.",
    },
    {
        "query": "Can our agreement be terminated early, and what are the conditions?",
        "sender_role": "supplier",
        "relevant_chunk_ids": None,
        "expected_verdict": "allowed",
        "expected_hard_constraint": False,
        "category": "supplier",
        "query_type": "factual",
        "notes": "Either party may terminate with 60 days notice; role=supplier variant.",
    },
]


# ─── Dataset assembly ─────────────────────────────────────────────────────────

def _assign_query_ids(entries: list[dict]) -> list[dict]:
    """Add sequential gt-NNN query_ids."""
    return [
        {"query_id": f"gt-{i + 1:03d}", **entry}
        for i, entry in enumerate(entries)
    ]


def generate(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(f"Dataset already exists at {OUTPUT_PATH}")
        print("Use --force to regenerate.")
        sys.exit(0)

    session = SessionLocal()
    llm = ChatOpenAI(
        model="gpt-4o",
        api_key=settings.OPENAI_API_KEY,
        temperature=0.0,
    )

    all_entries: list[dict] = []

    try:
        # ── Per-category generation ───────────────────────────────────────────
        for category, n in CATEGORY_TARGETS.items():
            print(f"  [{category}] loading chunks from DB ...")
            chunks: list[PolicyChunk] = (
                session.query(PolicyChunk)
                .filter(PolicyChunk.category == category)
                .order_by(PolicyChunk.page_number, PolicyChunk.chunk_index)
                .all()
            )

            if not chunks:
                print(f"  [{category}] WARNING: no chunks found — skipping.")
                continue

            print(f"  [{category}] {len(chunks)} chunks — generating {n} queries via GPT-4o ...")
            generated = _generate_for_category(llm, category, chunks, n)
            print(f"  [{category}] received {len(generated)} queries.")

            for q in generated:
                all_entries.append({
                    "query": q.query,
                    "sender_role": q.sender_role,
                    "relevant_chunk_ids": q.relevant_chunk_ids,
                    "expected_verdict": q.expected_verdict,
                    "expected_hard_constraint": q.expected_hard_constraint,
                    "category": category,
                    "query_type": q.query_type,
                    "notes": q.notes,
                })

        # ── Out-of-domain ─────────────────────────────────────────────────────
        print(f"  [out_of_domain] generating {OUT_OF_DOMAIN_COUNT} queries via GPT-4o ...")
        ood_queries = _generate_out_of_domain(llm, OUT_OF_DOMAIN_COUNT)
        print(f"  [out_of_domain] received {len(ood_queries)} queries.")

        for q in ood_queries:
            all_entries.append({
                "query": q.query,
                "sender_role": q.sender_role,
                "relevant_chunk_ids": [],
                "expected_verdict": "not_covered",
                "expected_hard_constraint": False,
                "category": "out_of_domain",
                "query_type": "out_of_domain",
                "notes": q.notes,
            })

        # ── Manual (existing) test cases ──────────────────────────────────────
        print(f"  [manual] appending {len(_MANUAL_CASES)} existing test cases ...")
        all_entries.extend(_MANUAL_CASES)

    finally:
        session.close()

    # ── Assign IDs and build final payload ────────────────────────────────────
    entries_with_ids = _assign_query_ids(all_entries)

    # Count stats
    verdict_counts: dict[str, int] = {}
    for e in entries_with_ids:
        v = e["expected_verdict"]
        verdict_counts[v] = verdict_counts.get(v, 0) + 1

    dataset = {
        "metadata": {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_used": "gpt-4o",
            "total_entries": len(entries_with_ids),
            "verdict_distribution": verdict_counts,
            "categories": list(CATEGORY_TARGETS.keys()) + ["out_of_domain"],
            "notes": (
                "Entries with relevant_chunk_ids=null are manual test cases where "
                "only verdict accuracy is evaluated (no retrieval benchmarking)."
            ),
        },
        "entries": entries_with_ids,
    }

    OUTPUT_PATH.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    print(f"\nDataset saved → {OUTPUT_PATH}")
    print(f"Total entries : {dataset['metadata']['total_entries']}")
    print(f"Verdict split : {verdict_counts}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a labelled ground truth dataset for policy RAG evaluation."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing dataset if present.",
    )
    args = parser.parse_args()
    generate(force=args.force)
