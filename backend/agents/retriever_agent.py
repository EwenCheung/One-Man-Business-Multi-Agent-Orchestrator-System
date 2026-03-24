"""
Internal Retriever Sub-Agent (PROPOSAL §4.2)

Retrieves internal business data with role-based access control.
Accepts a specific SubTask assigned by the Orchestrator, executes it,
and returns the completed task to be aggregated.

## TODO
- [ ] Connect to database (SQL / pgvector) via SQLAlchemy session
- [ ] Implement role-based retrieval filtering (sender_role determines what data is visible)
- [ ] Separate exact-match retrieval (SQL WHERE) from semantic retrieval (pgvector similarity)
- [ ] Return provenance with each result (source table, record ID, match type)
- [ ] Mark results as: verified_record | inferred_relevance | missing_data
- [ ] Add try/except with structured failure return
- [ ] Add timeout handling for DB queries
"""

from backend.graph.state import SubTask

# ────────────────────────────────────────────────────────
# Prompt — injected when this agent uses an LLM to
# interpret or summarize raw retrieval results.
# ────────────────────────────────────────────────────────
RETRIEVER_SYSTEM_PROMPT = """\
You are an Internal Data Retriever. Your ONLY job is to find and return
factual business data from the company database.

### Instructions
- Execute the retrieval task described below.
- Return ONLY data that matches the query. Do NOT fabricate records.
- For each result, indicate the source and match quality:
  - `exact_match` — direct SQL hit on a known field
  - `semantic_match` — vector similarity search result (include similarity score)
  - `no_match` — query returned no results
- If the sender's role restricts access to certain data, return `access_denied` for those fields.

### Role Access Rules
- Customers/Suppliers: NO access to internal margins, cost prices, or source code
- Investors: Access subject to NDA tier
- Owner: Full access

### Task
{task_description}

### Sender Role
{sender_role}
"""


def retriever_agent(task: SubTask) -> dict:
    """
    Execute the specific retrieval instructions.

    Input:  SubTask dict from Orchestrator fan-out
    Output: dict with 'completed_tasks' list to merge back to main state

    Functions needed (implement later):
    - _query_sql(task_description, sender_role) -> list[dict]
    - _query_vector(task_description, top_k=5) -> list[dict]
    - _filter_by_role(results, sender_role) -> list[dict]
    - _format_retrieval_result(results) -> str
    """
    # TODO: Replace stub with real retrieval logic
    completed_task = task.copy()
    completed_task["status"] = "completed"
    completed_task["result"] = f"(Stub) Retrieved data for instruction: {task['description']}"

    return {"completed_tasks": [completed_task]}
