"""
Orchestrator Supervisor Agent (PROPOSAL §4.1)

The Harness-Engineering Supervisor of the Multi-Agent architecture.
Performs constraint-based planning, dynamically delegates to isolated sub-agents,
evaluates results via self-validation loops, and handles failure tracking.
"""

import os
from typing import Literal, List
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from backend.config import settings

# ── SCHEMAS ────────────────────────────────────────────────────
class TaskDef(BaseModel):
    task_id: str = Field(description="Unique ID for this task (e.g. '1', '2')")
    description: str = Field(description="Highly specific instructions and constraints for the assigned agent.")
    assignee: Literal["retriever", "research", "policy", "memory"] = Field(description="The agent to execute this task.")
    priority: Literal["required", "optional"] = Field(description="Whether the pipeline should halt if this task fails.", default="required")
    depends_on: list[str] = Field(description="IDs of tasks that theoretically must happen first (helps your reasoning, though execution is parallel for now).", default=[])
    context_needed: list[str] = Field(description="List of specific context variables to inject (e.g., ['sender_role', 'urgency']). Drives selective injection.", default=[])


class OrchestratorDecision(BaseModel):
    """The structured output schema required from the Supervisor LLM."""
    reasoning: str = Field(description="Your step-by-step reasoning evaluating current state, constraints, and failures.")
    tasks: List[TaskDef] = Field(description="List of tasks to fan-out to sub-agents. Empty if routing to reply.", default=[])
    route_to_reply: bool = Field(description="Set to true ONLY if all required info is gathered and self-validation passes.")
    self_validation: str = Field(description="If routing to reply, explain how the gathered facts definitively answer the query safely.")
    identified_risks: list[str] = Field(description="Any risks or missing data handling strategies.", default=[])


# ── PROMPT TEMPLATE ────────────────────────────────────────────
system_prompt_template = """\
You are the Orchestrator (Supervisor) for a Role-Aware Multi-Agent system.
Your job is NOT to answer the user directly. Your job is Harness Engineering:
You decompose the user's request, delegate tight, isolated sub-tasks to Expert Agents,
and synthesize the results via constraint-based planning.

### Your Sub-Agents (The Executors)
1. `retriever` : Fetches internal databases, SQL records, or company inventory.
2. `research`  : Fetches external web searches or competitor comparisons.
3. `policy`    : Looks up company rules, pricing constraints, and disclosure boundaries.
4. `memory`    : Performs deep historical "grep-style" database searches for old logs/dates NOT found in short_term_memory.

### Workflow & Harness Engineering Rules
1. **Decompose & Assign:** If you need information, output a list of `tasks`. LangGraph executes them concurrently. Keep descriptions hyper-specific to bound the agent's context.
2. **Selective Context:** Use `context_needed` to dictate exactly what the sub-agent needs (e.g. if research agent doesn't need to know the customer's name, don't inject it).
3. **Failure Handling:** If a task in the `Failed Tasks` section failed, DO NOT blindly retry it. Analyze the logic failure, adjust the query, or try a different assignee.
4. **Self-Validation Loop:** Before setting `route_to_reply=True`, you MUST verify:
   - Do the completed tasks answer the core intent?
   - Did the policy agent clear any pricing/discount requests?
   - Is there any hallucinated data we must filter?
5. **Replan Limits:** You are on Replan Cycle {replan_count} of {max_replans}. If you hit the limit, you MUST set `route_to_reply=True` and draft a fallback/safe reply with what you have.

### Few-Shot Examples
**Example 1: Initial Request needing planning**
*State:* User asking for laptop discounts.
*Output:*
{{
  "reasoning": "Need to check laptop stock and bulk discount policy.",
  "tasks": [
    {{"task_id": "1", "description": "Fetch stock for laptops.", "assignee": "retriever", "priority": "required", "depends_on": [], "context_needed": ["raw_message"]}},
    {{"task_id": "2", "description": "Check discount policy for laptops.", "assignee": "policy", "priority": "required", "depends_on": [], "context_needed": ["sender_role"]}}
  ],
  "route_to_reply": false,
  "self_validation": "N/A",
  "identified_risks": ["Potential low stock"]
}}

**Example 2: Self-Validation (Ready to Reply)**
*State:* Completed Tasks successfully found stock and policy rules.
*Output:*
{{
  "reasoning": "Stock is sufficient and policy allows 15% discount.",
  "tasks": [],
  "route_to_reply": true,
  "self_validation": "We have facts from retriever (150 in stock) and policy (allowed 15%). Safe to reply.",
  "identified_risks": []
}}

### Core Business Rules
{rules_context}

### Context Envelope
- Sender: {sender_name} ({sender_role})
- Intent: {intent_label} | Urgency: {urgency_level}
- Original Message: {raw_message}
- Long-Term Preferences: {long_term_memory}
- Short-Term Chat History: {short_term_memory}

### Feedback Loop States
== COMPLETED TASKS ==
{completed_tasks_text}

== FAILED / QUARANTINED TASKS ==
{failed_tasks_text}
"""


def orchestrator_agent(state: dict) -> dict:
    """
    Supervisor routing: runs constraint-based planning, handles replan limits,
    and maps tasks to isolated sub-agents.
    """
    # 1. State tracking & Limit Enforcement
    replan_count = state.get("replan_count", 0)
    warnings = state.get("orchestrator_warnings", [])
    
    # Pre-emption: If we hit loop limits, force reply
    if replan_count >= settings.MAX_REPLAN_CYCLES:
        warnings.append(f"Max replan cycles ({settings.MAX_REPLAN_CYCLES}) reached. Forcing route to reply.")
        return {
            "active_tasks": [],
            "route_to_reply": True,
            "replan_count": replan_count,
            "plan_steps": ["Forced reply due to replan limit exhaustion."],
            "orchestrator_warnings": warnings
        }

    # 2. Format Feedback Loop States
    completed_tasks = state.get("completed_tasks", [])
    completed_text = "\n".join([f"Task {t['task_id']} ({t['assignee']}): {t['result']}" for t in completed_tasks])
    
    failed_tasks = state.get("failed_tasks", [])
    failed_text = "\n".join([f"Task {t['task_id']} ({t['assignee']}) FAILED: {t['result']}" for t in failed_tasks])

    prompt_kwargs = {
        "sender_name": state.get("sender_name", "Unknown"),
        "sender_role": state.get("sender_role", "Unknown"),
        "intent_label": state.get("intent_label", "Unknown"),
        "urgency_level": state.get("urgency_level", "Unknown"),
        "raw_message": state.get("raw_message", ""),
        "rules_context": state.get("rules_context", ""),
        "long_term_memory": state.get("long_term_memory", ""),
        "short_term_memory": state.get("short_term_memory", []),
        "completed_tasks_text": completed_text if completed_text else "None yet.",
        "failed_tasks_text": failed_text if failed_text else "None.",
        "replan_count": replan_count,
        "max_replans": settings.MAX_REPLAN_CYCLES
    }

    # 3. Call LLM Supervisor
    prompt = PromptTemplate.from_template(system_prompt_template)
    formatted_prompt = prompt.format(**prompt_kwargs)

    llm = ChatOpenAI(
        api_key=settings.OPENAI_API_KEY, 
        model=settings.LLM_MODEL, 
        temperature=0.0
    )
    router_llm = llm.with_structured_output(OrchestratorDecision)
    decision: OrchestratorDecision = router_llm.invoke(formatted_prompt)

    # 4. Harness Constraints & Fan-Out Mapping
    active_tasks = []
    
    # Enforce parallel task limit
    tasks_to_process = decision.tasks
    if len(tasks_to_process) > settings.MAX_PARALLEL_TASKS:
        warnings.append(f"LLM requested {len(tasks_to_process)} tasks. Truncating to max {settings.MAX_PARALLEL_TASKS}.")
        tasks_to_process = tasks_to_process[:settings.MAX_PARALLEL_TASKS]

    # Build the task DAG payload
    for t in tasks_to_process:
        active_tasks.append({
            "task_id": t.task_id,
            "description": t.description,
            "assignee": t.assignee,
            "status": "pending",
            "result": "",
            "priority": t.priority,
            "context_needed": t.context_needed,
            "depends_on": t.depends_on
        })

    # Prepare tracking logs
    step_log = (
        f"Cycle {replan_count}: {decision.reasoning}\n"
        f"Validation: {decision.self_validation}\n"
        f"Routed to reply: {decision.route_to_reply} | Tasks generated: {len(active_tasks)}"
    )

    # 5. Return updated state
    return {
        "active_tasks": active_tasks,
        "route_to_reply": decision.route_to_reply,
        "replan_count": replan_count + 1 if not decision.route_to_reply else replan_count,
        "plan_steps": [step_log],
        "orchestrator_warnings": warnings
    }