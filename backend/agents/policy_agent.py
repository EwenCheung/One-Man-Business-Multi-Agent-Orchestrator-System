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

from backend.config import settings
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
            "One of: 'allowed', 'disallowed', 'requires_approval', 'not_covered'. "
            "Determine this from the policy text. "
            "'cannot X unless owner approval' → requires_approval. "
            "'permitted within guidelines' → allowed. "
            "Then: if verdict is 'requires_approval' AND the excerpt it is based on has "
            "hard_constraint=True, change to 'disallowed'. Only check the primary excerpt — "
            "not incidental excerpts from other categories."
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
            "True if the excerpt your verdict is based on has hard_constraint=True. "
            "Copy from the metadata of the primary answering excerpt — do not derive from the verdict. "
            "An 'allowed' verdict can have hard_constraint=True."
        )
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description=(
            "'high' — an excerpt DIRECTLY and UNAMBIGUOUSLY answers the exact question asked; "
            "'medium' — excerpts are relevant but require interpretation or inference to apply; "
            "'low' — no excerpt closely matches the question; verdict is inferred from indirect evidence. "
            "Default to 'medium' when uncertain. Only use 'high' when the match is direct and explicit."
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
You are a Policy Evaluator for a small business. Your job is to classify whether
a described action or request is permitted, prohibited, or requires approval,
based solely on the policy excerpts provided below.

Each excerpt is tagged with hard_constraint=True or hard_constraint=False. This flag
has one specific effect on the verdict and separately determines the hard_constraint
output field. Follow the three steps below in order.

### Step 1 — Read the policy text and determine the initial verdict
Based on what the policy text says, classify the action as one of:
- 'allowed'           — the policy explicitly permits the action
- 'disallowed'        — the policy explicitly prohibits the action with no escape path
- 'requires_approval' — the policy says the action can proceed with owner sign-off
- 'not_covered'       — no excerpt addresses the question at all

Reading rules for ambiguous text:
- "X cannot be done unless owner approval" → requires_approval (the approval path exists)
- "X is not permitted by default; requires a separate agreement/addendum" → requires_approval
- "X is permitted within guidelines" → allowed, even if unauthorized X is also mentioned as prohibited
- "X is prohibited under any circumstances / at all times" → disallowed

### Step 2 — Apply the hard_constraint override (only affects requires_approval)
If your Step 1 verdict is 'requires_approval', check the excerpt your verdict is
BASED ON (the one cited in supporting_rules). If THAT excerpt has hard_constraint=True,
change the verdict to 'disallowed'.
Do NOT trigger this override based on an incidental excerpt from a different policy
category that was not the basis for your verdict decision.

### Step 3 — Set the hard_constraint output field (independent of the verdict)
Set hard_constraint=True if the excerpt your verdict is based on has hard_constraint=True.
Do NOT derive this from your verdict — an 'allowed' verdict can have hard_constraint=True.

### Confidence calibration
- 'high'   — an excerpt DIRECTLY and UNAMBIGUOUSLY answers the exact question.
- 'medium' — excerpts are relevant but require interpretation or inference to apply.
- 'low'    — no excerpt closely matches; verdict is inferred from indirect evidence.
When uncertain between 'high' and 'medium', choose 'medium'.

### Rules
- Base your verdict ONLY on the excerpts. Do NOT invent policies.
- If no excerpt addresses the question, return verdict = 'not_covered'.
- The sender's role may affect which policies apply — consider it carefully.

### Policy Excerpts
{policy_excerpts}

### Policy Question
{task_description}

### Sender Role
{sender_role}
"""


# ─── Private helpers ──────────────────────────────────────────────────────────


def _retrieve(
    session, description: str, sender_role: str, owner_id: str
) -> list[dict[str, object]]:
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
        owner_id=owner_id,
        category=categories[0] if len(categories) == 1 else None,
        categories=categories or None,
    )
    lexical_candidates = search_policy_chunks_lexical(
        session, description, categories=categories or None, owner_id=owner_id
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
            f"[{i + 1}] (source: {c['source_file']}, category: {c['category']},"
            f" page {c['page_number']}, section: {c.get('subheading') or 'N/A'},"
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


def _normalize_verdict_for_sender_role(
    decision: PolicyDecision,
    *,
    sender_role: str,
    description: str,
) -> PolicyDecision:
    normalized_role = (sender_role or "").strip().lower()
    description_text = (description or "").lower()
    support_text = " ".join(decision.supporting_rules).lower()

    if (
        normalized_role == "customer"
        and decision.verdict == "requires_approval"
        and "owner" in support_text
        and any(keyword in description_text for keyword in ("stack", "combine", "both"))
    ):
        return decision.model_copy(
            update={
                "verdict": "disallowed",
                "explanation": (
                    "The policy allows this only with owner approval, so for a customer request "
                    "the action is not permitted directly. " + decision.explanation
                ),
            }
        )

    return decision


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
    owner_id = ctx.get("owner_id", settings.OWNER_ID)

    logger.info("PolicyAgent: starting task '%s' | role=%s", task.get("task_id"), sender_role)

    completed_task = dict(task)

    session = SessionLocal()
    try:
        llm = get_chat_llm(scope="policy", temperature=0.0)

        # Stage 1 + 2: retrieve and rerank
        chunks = _retrieve(session, description, sender_role, owner_id)

        # Stage 3: evaluate
        decision = _evaluate(description, chunks, sender_role, llm)
        decision = _normalize_verdict_for_sender_role(
            decision,
            sender_role=sender_role,
            description=description,
        )

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
