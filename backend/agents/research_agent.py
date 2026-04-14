"""
External Research Sub-Agent (PROPOSAL §4.3)

Performs bounded external web search when the Orchestrator determines that
internal retrieval is insufficient. Accepts a specific SubTask assigned by
the Orchestrator and returns its result as a completed task.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from backend.graph.state import SubTask
from backend.models.agent_response import AgentResponse
from backend.agents.tools.skills import SkillsLoader
from backend.config import settings
from backend.utils.llm_provider import get_chat_llm
from backend.graph.state import SubTask


RESEARCH_SYSTEM_PROMPT = """\
You are an External Research Agent. Your job is to summarize web search
results relevant to a specific business question.

### Instructions
- Summarize ONLY what the search results say. Do NOT add your own knowledge.
- For each finding, classify it:
  - `sourced` — directly stated in a search result (include URL)
  - `inferred` — reasonable inference from multiple sources (state your reasoning)
  - `unresolved` — the search results do not answer this part of the question
- Do NOT override any internal business data with external findings.
- Keep summaries concise — bullet points preferred.

### Search Results
{search_results}

### Research Question
{task_description}
"""

logger = logging.getLogger(__name__)

_skills_loader = SkillsLoader(workspace=Path(__file__).parent)

# Composed skill contexts injected per prompt
_QUERY_SKILL_CONTEXT = _skills_loader.load_skills_for_context([
    "query-formulation",
    "scope-boundaries",
    "stakeholder-framing",
])

_SYNTHESIS_SKILL_CONTEXT = _skills_loader.load_skills_for_context([
    "source-evaluation",
    "synthesis",
    "confidence-calibration",
    "scope-boundaries",
    "stakeholder-framing",
    "market-pricing-research",
    "competitor-intelligence",
    "regulatory-compliance-research",
])


_MAX_SEARCH_RESULTS = 3  # Number of Tavily results to fetch per query
_MAX_QUERIES = 2         # Maximum distinct queries to run against Tavily for one task


class SearchQueries(BaseModel):
    """Tight search queries extracted from the Orchestrator's task description.

    The ``_MAX_QUERIES`` cap is enforced downstream via a slice rather than a
    Pydantic field constraint, keeping the schema compatible with both
    Pydantic v1 and v2.
    """
    queries: list[str] = Field(
        description=(
            f"List of {_MAX_QUERIES} or fewer concise web search queries (4-8 words each) "
            "that together cover the task. Ordered from most to least important."
        ),
    )


class ResearchSummary(BaseModel):
    """Structured findings produced after synthesising Tavily search results."""
    key_findings: list[str] = Field(
        description=(
            "Bullet-point list of the most relevant facts found. "
            "Each item must be a single, concrete, attributable fact."
        )
    )
    sources: list[str] = Field(
        description="Source URLs or publication names for the findings.",
        default_factory=list,
    )
    confidence: str = Field(
        description=(
            "Assign based strictly on source count and domain match — "
            "not on how detailed or authoritative a single source is. "
            "FIRST: if results are from the wrong geography or wrong domain/sector for the task, "
            "assign 'low' regardless of result quality. "
            "OTHERWISE: "
            "'high' — 2 or more independent credible sources corroborate the same specific fact. "
            "'medium' — exactly 1 credible primary source answers the task, even if that source "
            "is highly authoritative (e.g. HMRC, GOV.UK, official bodies — 1 source is still 'medium'). "
            "'low' — no relevant results found, results are indirect or stale, or results are "
            "from the wrong geography or sector for the task."
        )
    )
    caveat: Optional[str] = Field(
        default=None,
        description=(
            "A specific, identified limitation in the results. "
            "Set to None when results completely answer the task with no gaps, "
            "staleness, contradictions, or scope issues — do not add a general disclaimer. "
            "Only populate when at least one of these is true: "
            "(1) part of the task was not answered by any result, "
            "(2) sources are stale or flagged as potentially out of date, "
            "(3) results are from the wrong domain or geography, "
            "(4) two sources contradict each other, "
            "(5) results are indirect or from low-trust sources."
        ),
    )


_QUERY_EXTRACTION_TEMPLATE = """\
You are a search query specialist working inside a business AI system.
Your job is to convert a research task description into tight, effective web search queries.

══════════════════════════════════════════════════════════════════
RESEARCH SKILL — Methodology & Constraints
══════════════════════════════════════════════════════════════════
{skill_context}

══════════════════════════════════════════════════════════════════
TASK
══════════════════════════════════════════════════════════════════
Convert the following task description into up to {max_queries} focused search queries.

{task_description}
"""

_SYNTHESIS_TEMPLATE = """\
You are synthesising web search results for a business AI system.
The findings you produce will be read by a Reply Agent drafting a message to a {sender_role}.

══════════════════════════════════════════════════════════════════
RESEARCH SKILL — Methodology & Constraints
══════════════════════════════════════════════════════════════════
{skill_context}

══════════════════════════════════════════════════════════════════
RESEARCH TASK
══════════════════════════════════════════════════════════════════
{task_description}

══════════════════════════════════════════════════════════════════
RAW SEARCH RESULTS
══════════════════════════════════════════════════════════════════
{raw_results}

══════════════════════════════════════════════════════════════════
CONFIDENCE ASSIGNMENT — Apply the first matching rule
══════════════════════════════════════════════════════════════════

confidence = "low" if ANY of these is true:
  • No relevant results found.
  • The product category / industry sector of the sources does not match the
    product category / industry sector of the task.
    (e.g. task asks about electronics margins; sources are about automotive
    parts — these are different sectors even though both sell "accessories")
  • The geography of the sources does not match the geography of the task.
    (e.g. task asks for UK data; sources cover the US market only)
  • Results are only indirect, stale, or from low-trust sources.

confidence = "high" ONLY when ALL THREE conditions are true simultaneously:
  1. Sources are from the correct sector and geography for the task.
  2. Every question and sub-question in the task description is answered
     by the results. If any part is unanswered, "high" is NOT permitted.
  3. Two or more INDEPENDENT source URLs corroborate the same specific fact.
     Count distinct "(source: ...)" URLs — a single source with many data
     points is still ONE source and cannot qualify for "high".

confidence = "medium" in all other cases, including:
  • Exactly 1 source answers the task fully.
  • 2+ sources exist but at least one sub-question is unanswered.
  • Authoritative single sources (HMRC, GOV.UK, official bodies) — authority
    does not substitute for corroboration; 1 authoritative source = "medium".

══════════════════════════════════════════════════════════════════
CAVEAT ASSIGNMENT — Default is null/None
══════════════════════════════════════════════════════════════════
Only populate caveat when you can state a specific, identifiable problem:
  • Name a sub-question from the task that no result answered.
  • Name a source that explicitly flags its data as stale or subject to review.
  • Describe the exact domain or geography mismatch if confidence = "low".
  • Describe the contradiction if two sources give conflicting figures.
Do NOT write generic disclaimers ("verify with primary sources", "data may
change", "may not reflect all conditions"). If none of the above apply,
set caveat to null/None.

══════════════════════════════════════════════════════════════════
TASK
══════════════════════════════════════════════════════════════════
Apply the Research Skill methodology above to synthesise the raw results into
structured findings for a {sender_role} context.
"""


def _extract_queries(task_description: str, llm: BaseChatModel) -> list[str]:
    """Convert a verbose Orchestrator task description into focused search queries.

    Uses a single ``with_structured_output`` LLM call — cheaper and faster than
    a full chat turn because there is no back-and-forth; the model returns a
    validated ``SearchQueries`` object directly.

    Falls back to the first sentence of the task description if the LLM call
    fails, ensuring the search step always receives at least one query.

    Args:
        task_description: The raw task description string assigned by the
            Orchestrator (e.g. "Search the web for Competitor X's latest
            product release and summarise key specs.").
        llm: A chat LLM instance used to perform the extraction.

    Returns:
        A list of 1–``_MAX_QUERIES`` concise search query strings, ordered
        from most to least important. Never empty.
    """
    query_llm = llm.with_structured_output(SearchQueries)
    prompt = PromptTemplate.from_template(_QUERY_EXTRACTION_TEMPLATE)
    formatted = prompt.format(
        task_description=task_description,
        max_queries=_MAX_QUERIES,
        skill_context=_QUERY_SKILL_CONTEXT,
    )
    try:
        result = query_llm.invoke(formatted)
        queries = [q.strip() for q in result.queries if q.strip()]
        logger.debug("ResearchAgent: extracted queries — %s", queries)
        return queries[:_MAX_QUERIES]
    except Exception as exc:
        logger.warning(
            "ResearchAgent: query extraction failed (%s) — falling back to task description",
            exc,
        )
        fallback = task_description.split(".")[0].strip()[:80]
        return [fallback]


def _run_tavily_search(queries: list[str]) -> str:
    """Execute a list of queries directly against the Tavily search API.

    Tavily is called as a plain HTTP client — there is no LLM involvement at
    this step. Each query is run independently and all results are concatenated
    into a single string for the synthesis step.

    Per-query errors are caught and recorded as inline error markers so that
    a single failing query does not abort the entire search.

    Args:
        queries: A list of concise search query strings produced by
            ``_extract_queries``.

    Returns:
        A single string containing all result snippets separated by ``---``
        dividers, or a human-readable ``[unavailable]`` / ``[error]`` message
        if Tavily cannot be reached. Never raises.
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        logger.warning("tavily-python not installed. Run: pip install tavily-python")
        return "[web search unavailable — install tavily-python]"

    api_key = settings.TAVILY_API_KEY
    if not api_key:
        logger.warning("ResearchAgent: TAVILY_API_KEY not configured")
        return "[web search unavailable — TAVILY_API_KEY not set]"

    client = TavilyClient(api_key=api_key)
    snippets = []

    for query in queries:
        logger.debug("ResearchAgent: Tavily query — '%s'", query)
        try:
            response = client.search(
                query=query,
                max_results=_MAX_SEARCH_RESULTS,
                search_depth="basic",
            )
            for r in response.get("results", []):
                snippets.append(
                    f"[{r.get('title', 'No title')}] "
                    f"{r.get('content', '')[:400]} "
                    f"(source: {r.get('url', 'unknown')})"
                )
        except Exception as exc:
            logger.warning("ResearchAgent: Tavily error for query '%s' — %s", query, exc)
            snippets.append(f"[search error for '{query}': {exc}]")

    return "\n\n---\n\n".join(snippets) if snippets else "No relevant results found."


def _synthesise(
    task_description: str,
    raw_results: str,
    llm: BaseChatModel,
    sender_role: str = "unknown",
) -> ResearchSummary:
    """Distil raw Tavily results into a structured ``ResearchSummary``.

    This is the only LLM call that reads the search data. It uses
    ``with_structured_output`` so the model is constrained to return a
    validated ``ResearchSummary`` object — no free-form text to parse.

    The ``sender_role`` is injected into the synthesis prompt so the model
    can prioritise findings that are most relevant to the stakeholder type
    (e.g. ROI benchmarks for an investor vs competitor specs for a partner).

    On failure a low-confidence fallback summary is returned so the pipeline
    can continue and surface a caveat to the Orchestrator rather than crash.

    Args:
        task_description: The original Orchestrator task description, included
            in the prompt so the LLM can filter results by relevance.
        raw_results: Concatenated Tavily result snippets produced by
            ``_run_tavily_search``.
        llm: A chat LLM instance used to perform the synthesis.
        sender_role: The stakeholder type from ``PipelineState.sender_role``
            (e.g. ``"investor"``, ``"supplier"``). Defaults to ``"unknown"``.
            Used to focus synthesis on findings relevant to the reply context.

    Returns:
        A ``ResearchSummary`` with key findings, sources, a confidence rating,
        and an optional caveat. On LLM failure, returns a ``confidence="low"``
        summary describing the error.
    """
    synthesis_llm = llm.with_structured_output(ResearchSummary)
    prompt = PromptTemplate.from_template(_SYNTHESIS_TEMPLATE)
    formatted = prompt.format(
        task_description=task_description,
        raw_results=raw_results,
        sender_role=sender_role,
        skill_context=_SYNTHESIS_SKILL_CONTEXT,
    )
    try:
        summary = synthesis_llm.invoke(formatted)
        return summary
    except Exception as exc:
        logger.error("ResearchAgent: synthesis failed — %s", exc)
        return ResearchSummary(
            key_findings=[f"Research attempted but synthesis failed: {exc}"],
            sources=[],
            confidence="low",
            caveat="Synthesis step raised an error. Raw results may still be in logs.",
        )


def _format_result(summary: ResearchSummary) -> str:
    """Render a ``ResearchSummary`` as a human-readable text block.

    The formatted string is written into ``SubTask["result"]`` so the
    Orchestrator and Reply Agent can read it directly from ``completed_tasks``
    without needing to deserialise a structured object.

    Args:
        summary: A ``ResearchSummary`` instance produced by ``_synthesise``.

    Returns:
        A multi-line string containing the confidence level, a bulleted list
        of key findings, a list of sources, and an optional caveat.
    """
    lines: list[str] = [f"Confidence: {summary.confidence.upper()}"]

    if summary.key_findings:
        lines.append("\nKey Findings:")
        for finding in summary.key_findings:
            lines.append(f"  • {finding}")

    if summary.sources:
        lines.append("\nSources:")
        for src in summary.sources:
            lines.append(f"  - {src}")

    if summary.caveat:
        lines.append(f"\nCaveat: {summary.caveat}")

    return "\n".join(lines)


def research_agent(task: SubTask, sender_role: str = "unknown") -> dict:
    """Execute external web research for a SubTask assigned by the Orchestrator.

    This function is the public entry point called by the LangGraph fan-out
    node for every ``SubTask`` with ``assignee="research"``. It runs three
    sequential steps — query extraction, Tavily search, and synthesis — and
    returns the completed task in a format compatible with LangGraph's
    ``Annotated[list, operator.add]`` fan-in reducer.

    Pipeline
    ────────
    1. Query extraction  — LLM converts the verbose task description into
                           ``_MAX_QUERIES`` focused search queries.
    2. Tavily search     — queries executed directly against the Tavily API
                           (no LLM involvement at this step).
    3. Synthesis         — LLM condenses raw results into a structured
                           ``ResearchSummary`` with findings, sources, and
                           a confidence rating.
    4. Format & return   — summary serialised to plain text and written back
                           into the completed ``SubTask``.

    Args:
        task: A ``SubTask`` dict assigned by the Orchestrator, containing:
            - ``task_id``    (str): Unique identifier for this task.
            - ``description``(str): Specific research instructions.
            - ``assignee``   (str): Must be ``"research"`` for this agent.
            - ``status``     (str): ``"pending"`` on entry.
            - ``result``     (str): Empty string on entry; populated on return.
        sender_role: The stakeholder type from ``PipelineState.sender_role``
            (e.g. ``"investor"``, ``"supplier"``). Passed through to the
            synthesis step so findings are prioritised for the reply context.
            Defaults to ``"unknown"`` if not provided by the caller.

    Returns:
        A dict with a single key ``"completed_tasks"`` containing a one-item
        list with the updated ``SubTask`` (``status="completed"``,
        ``result=<formatted findings>``). LangGraph's reducer merges this list
        into the main ``PipelineState.completed_tasks`` automatically.
    """
    task_description = task["description"]

    # Extract sender_role from injected_context if available
    injected = task.get("injected_context", {})
    if injected.get("sender_role"):
        sender_role = injected["sender_role"]

    logger.info("ResearchAgent: starting task '%s' — %s", task["task_id"], task_description)

    llm = get_chat_llm(temperature=0.0)

    try:
        # 1. Extract focused search queries from the task description
        queries = _extract_queries(task_description, llm)

        # 2. Call Tavily web search API directly (no LLM)
        raw_results = _run_tavily_search(queries)

        # 3. Synthesise raw results into structured findings
        summary = _synthesise(task_description, raw_results, llm, sender_role)

        # 4. Format for the Orchestrator / Reply Agent
        result_text = _format_result(summary)

        logger.info(
            "ResearchAgent: task '%s' complete | confidence=%s | findings=%d",
            task["task_id"], summary.confidence, len(summary.key_findings),
        )

        agent_response = AgentResponse(
            status="success",
            confidence=summary.confidence,
            result=result_text,
            facts=summary.key_findings,
            unknowns=[],
            constraints=[]
        )

        completed_task = dict(task)
        completed_task["status"] = "completed"
        completed_task["result"] = agent_response.model_dump_json()

    except Exception as exc:
        logger.error("ResearchAgent: unexpected error on task '%s' — %s", task["task_id"], exc)
        agent_response = AgentResponse(
            status="failed",
            confidence="low",
            result=f"Research agent failed: {exc}",
            unknowns=[str(exc)],
        )
        completed_task = dict(task)
        completed_task["status"] = "failed"
        completed_task["result"] = agent_response.model_dump_json()

    return {"completed_tasks": [completed_task]}
