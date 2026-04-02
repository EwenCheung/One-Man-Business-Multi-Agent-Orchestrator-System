"""
Policy Sub-Agent (PROPOSAL §4.4)

RAG-based policy lookup agent. Retrieves relevant chunks from the policy_chunks
pgvector table, reranks them with an LLM cross-encoder, then evaluates the
original question against the top-N chunks to produce a structured verdict.

Pipeline
────────
1. Search   — embed the query, pgvector cosine similarity → top-K candidates
2. Rerank   — LLM cross-encoder scores each candidate → top-N most relevant
3. Evaluate — LLM reads top-N chunks + question → PolicyDecision (structured output)
4. Format   — verdict serialised to plain text and written to SubTask result
"""

import logging
from typing import Literal, Optional

from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from backend.db.engine import SessionLocal
from backend.graph.state import SubTask
from backend.models.agent_response import AgentResponse
from backend.tools.policy_tools import (
    infer_policy_categories,
    merge_policy_candidates,
    rerank_chunks,
    search_policy_chunks,
    search_policy_chunks_lexical,
)
from backend.utils.llm_provider import get_chat_llm

logger = logging.getLogger(__name__)


# ─── Output schema ─────────────────────────────────────────────────


class PolicyDecision(BaseModel):
    """Structured policy evaluation result produced by the LLM."""

    verdict: str = Field(
        description=(
            "One of: 'allowed' — the action is permitted by policy; "
            "'disallowed' — the action violates a hard constraint (cite the rule); "
            "'requires_approval' — the action needs owner sign-off before proceeding; "
            "'not_covered' — no existing policy addresses this situation."
        )
    )
    explanation: str = Field(
        description=(
            "A concise explanation of the verdict, grounded only in the provided "
            "policy excerpts. Do not invent rules or soften hard constraints."
        )
    )
    supporting_rules: list[str] = Field(
        default_factory=list,
        description=(
            "Direct quotes or close paraphrases from the policy excerpts that "
            "support the verdict. Empty list if verdict is 'not_covered'."
        ),
    )
    hard_constraint: bool = Field(
        description=(
            "True if any matching rule is marked as a hard constraint that cannot "
            "be overridden even with approval."
        )
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "'high' — one or more excerpts directly address the question; "
            "'medium' — excerpts are relevant but require interpretation; "
            "'low' — no excerpts closely match the question."
        )
    )
    caveat: Optional[str] = Field(
        default=None,
        description=(
            "Any important limitation, ambiguity, or gap the Orchestrator should "
            "know about — e.g. the question spans multiple policies."
        ),
    )


# ─── Prompt ───────────────────────────────────────────────────────────────────

_EVALUATION_TEMPLATE = """\
You are a Policy Evaluator for a small business. Your job is to determine whether
a described action or request is permitted, disallowed, or requires approval,
based solely on the policy excerpts provided below.

### Rules
- Base your verdict ONLY on the excerpts. Do NOT invent policies.
- Do NOT soften or reinterpret hard constraints.
- If no excerpt addresses the question, return verdict = 'not_covered'.
- The sender's role may affect which policies apply — consider it when evaluating.

### Policy Excerpts
{policy_excerpts}

### Policy Question
{task_description}

### Sender Role
{sender_role}
"""


# ─── Private helpers ──────────────────────────────────────────────────────────


def _retrieve(session, description: str, sender_role: str) -> list[dict[str, object]]:
    """
    Run the two-stage retrieval pipeline for a policy question.

    Stage 1: pgvector cosine similarity search → top-K candidates.
    Stage 2: LLM reranker → top-N most contextually relevant chunks.

    The category filter is intentionally omitted here so the agent can match
    across all policy domains. The orchestrator can narrow scope via the task
    description if needed.

    Args:
        session:     SQLAlchemy session.
        description: Natural language policy question from the SubTask.
        sender_role: Stakeholder type — logged for traceability.

    Returns:
        Reranked list of chunk dicts (up to POLICY_TOP_N entries).
    """
    logger.debug("PolicyAgent: searching chunks for role=%s | query='%s'", sender_role, description)
    categories = infer_policy_categories(description, sender_role)
    semantic_candidates = search_policy_chunks(
        session,
        description,
        category=categories[0] if len(categories) == 1 else None,
        categories=categories or None,
    )
    lexical_candidates = search_policy_chunks_lexical(
        session, description, categories=categories or None
    )
    candidates = merge_policy_candidates(semantic_candidates, lexical_candidates)
    logger.debug(
        "PolicyAgent: retrieved %d merged candidates (semantic=%d lexical=%d)",
        len(candidates),
        len(semantic_candidates),
        len(lexical_candidates),
    )

    ranked = rerank_chunks(description, candidates)
    logger.debug("PolicyAgent: reranked to %d chunks", len(ranked))

    return ranked


def _evaluate(
    description: str,
    chunks: list[dict[str, object]],
    sender_role: str,
    llm,
) -> PolicyDecision:
    """
    Evaluate a policy question against the reranked chunks.

    Passes the chunks as numbered excerpts to the LLM via structured output.
    On failure, returns a low-confidence 'not_covered' fallback so the pipeline
    does not crash.

    Args:
        description: The original policy question.
        chunks:      Reranked chunks from the retrieval stage.
        sender_role: Stakeholder type injected into the evaluation prompt.
        llm:         Chat LLM instance.

    Returns:
        A ``PolicyDecision`` with verdict, explanation, and metadata.
    """
    structured_llm = llm.with_structured_output(PolicyDecision)

    if chunks:
        excerpts = "\n\n---\n\n".join(
            f"[{i + 1}] (source: {c['source_file']}, page {c['page_number']},"
            f" section: {c.get('subheading') or 'N/A'},"
            f" retrieval_mode={c.get('retrieval_mode', 'semantic')},"
            f" hard_constraint={c['hard_constraint']})\n{c['chunk_text']}"
            for i, c in enumerate(chunks)
        )
    else:
        excerpts = "[No relevant policy excerpts found.]"

    prompt = PromptTemplate.from_template(_EVALUATION_TEMPLATE)
    formatted = prompt.format(
        policy_excerpts=excerpts,
        task_description=description,
        sender_role=sender_role,
    )

    try:
        decision: PolicyDecision = structured_llm.invoke(formatted)
        return decision
    except Exception as exc:
        logger.error("PolicyAgent: evaluation failed — %s", exc)
        return PolicyDecision(
            verdict="not_covered",
            explanation=f"Policy evaluation failed due to an internal error: {exc}",
            supporting_rules=[],
            hard_constraint=False,
            confidence="low",
            caveat="Evaluation step raised an error. Manual policy review recommended.",
        )


def _format_result(decision: PolicyDecision) -> str:
    """
    Serialise a PolicyDecision as a human-readable text block.

    Written into SubTask["result"] so the Orchestrator and Reply Agent can read
    it directly from completed_tasks without deserialising a structured object.
    """
    lines: list[str] = [
        f"Verdict:    {decision.verdict.upper()}",
        f"Confidence: {decision.confidence.upper()}",
        f"Hard Constraint: {'YES' if decision.hard_constraint else 'NO'}",
        f"\nExplanation:\n{decision.explanation}",
    ]

    if decision.supporting_rules:
        lines.append("\nSupporting Rules:")
        for rule in decision.supporting_rules:
            lines.append(f"  • {rule}")

    if decision.caveat:
        lines.append(f"\nCaveat: {decision.caveat}")

    return "\n".join(lines)


# ─── Public entry point ───────────────────────────────────────────────────────


def policy_agent(task: SubTask) -> dict[str, list[dict[str, object]]]:
    """
    Execute a policy lookup SubTask assigned by the Orchestrator.

    Pipeline:
        1. Extract question and sender context from the SubTask.
        2. Retrieve top-K chunks via pgvector cosine search.
        3. Rerank to top-N via LLM cross-encoder.
        4. Evaluate the question against top-N chunks → PolicyDecision.
        5. Serialise result and return as completed SubTask.

    Args:
        task: SubTask dict from the Orchestrator fan-out. Expected fields:
              ``task_id``, ``description``, ``assignee="policy"``,
              ``status="pending"``, ``injected_context`` (with ``sender_role``).

    Returns:
        Dict with ``"completed_tasks"`` list for LangGraph fan-in reducer.
    """
    description = task.get("description", "")
    ctx = task.get("injected_context", {})
    sender_role = ctx.get("sender_role", "unknown")

    logger.info("PolicyAgent: starting task '%s' | role=%s", task.get("task_id"), sender_role)

    completed_task = dict(task)

    session = SessionLocal()
    try:
        llm = get_chat_llm(scope="policy", temperature=0.0)

        # Stage 1 + 2: retrieve and rerank
        chunks = _retrieve(session, description, sender_role)

        # Stage 3: evaluate
        decision = _evaluate(description, chunks, sender_role, llm)

        # Stage 4: format
        result_text = _format_result(decision)

        logger.info(
            "PolicyAgent: task '%s' complete | verdict=%s | confidence=%s",
            task.get("task_id"),
            decision.verdict,
            decision.confidence,
        )

        agent_response = AgentResponse(
            status="success",
            confidence=decision.confidence,
            result=result_text,
            facts=decision.supporting_rules,
            unknowns=[decision.caveat] if decision.caveat else [],
            constraints=["HARD CONSTRAINT: " + r for r in decision.supporting_rules]
            if decision.hard_constraint
            else [],
        )

        completed_task["status"] = "completed"
        completed_task["result"] = agent_response.model_dump_json()

    except Exception as exc:
        logger.error("PolicyAgent: unexpected error on task '%s' — %s", task.get("task_id"), exc)
        agent_response = AgentResponse(
            status="failed",
            confidence="low",
            result=f"Policy agent failed: {exc}",
            unknowns=[str(exc)],
        )
        completed_task["status"] = "failed"
        completed_task["result"] = agent_response.model_dump_json()
    finally:
        session.close()

    return {"completed_tasks": [completed_task]}
