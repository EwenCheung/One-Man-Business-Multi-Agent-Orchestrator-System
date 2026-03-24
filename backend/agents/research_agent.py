"""
External Research Sub-Agent (PROPOSAL §4.3)

Performs bounded external search if internal retrieval is insufficient.
Accepts a specific SubTask assigned by the Orchestrator.

## TODO
- [ ] Integrate web search API (Tavily / SerpAPI / Brave Search)
- [ ] Implement search result summarization via LLM
- [ ] Clearly separate: sourced_findings | inferred_observations | unresolved_uncertainty
- [ ] Include source URLs with every finding
- [ ] Enforce bounded scope — do NOT broaden the search beyond the task
- [ ] Add try/except with structured failure return
- [ ] Add timeout for external API calls
- [ ] Rate-limit external searches to control cost
"""

from backend.graph.state import SubTask

# ────────────────────────────────────────────────────────
# Prompt — used to summarize raw search results
# ────────────────────────────────────────────────────────
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


def research_agent(task: SubTask) -> dict:
    """
    Execute external web search or competitor lookup.

    Input:  SubTask dict from Orchestrator fan-out
    Output: dict with 'completed_tasks' list to merge back to main state

    Functions needed (implement later):
    - _web_search(query, max_results=5) -> list[dict]  # Call search API
    - _summarize_results(raw_results, question) -> str  # LLM summarization
    - _format_research_output(summary, sources) -> str
    """
    # TODO: Replace stub with real web search + summarization
    completed_task = task.copy()
    completed_task["status"] = "completed"
    completed_task["result"] = f"(Stub) External research complete for: {task['description']}"

    return {"completed_tasks": [completed_task]}
