"""
Orchestrator Supervisor Agent (PROPOSAL §4.1)

The Harness-Engineering Supervisor of the Multi-Agent architecture.
Performs constraint-based planning, dynamically delegates to isolated sub-agents,
evaluates results via self-validation loops, and handles failure tracking.
"""

import os
from typing import Any, Literal, List, cast
from pydantic import BaseModel, Field

from langchain_core.prompts import PromptTemplate

from backend.config import settings
from backend.graph.state import PipelineState
from backend.utils.context_compression import compress_context, reset_circuit_breaker
from backend.utils.llm_provider import get_chat_llm
from backend.utils.pipeline_guards import (
    check_replan_limit,
    check_parallel_task_limit,
    reset_permission_denials,
)


# ── SCHEMAS ────────────────────────────────────────────────────
class TaskDef(BaseModel):
    task_id: str = Field(description="Unique ID for this task (e.g. '1', '2')")
    description: str = Field(
        description="Highly specific instructions and constraints for the assigned agent."
    )
    assignee: Literal["retriever", "research", "policy", "memory"] = Field(
        description="The agent to execute this task."
    )
    priority: Literal["required", "optional"] = Field(
        description="Whether the pipeline should halt if this task fails.", default="required"
    )
    depends_on: list[str] = Field(
        description="IDs of tasks that theoretically must happen first (helps your reasoning, though execution is parallel for now).",
        default=[],
    )
    context_needed: list[str] = Field(
        description="List of specific context variables to inject (e.g., ['sender_role', 'urgency']). Drives selective injection.",
        default=[],
    )


class OrchestratorDecision(BaseModel):
    """The structured output schema required from the Supervisor LLM."""

    reasoning: str = Field(
        description="Your step-by-step reasoning evaluating current state, constraints, and failures."
    )
    tasks: List[TaskDef] = Field(
        description="List of tasks to fan-out to sub-agents. Empty if routing to reply.", default=[]
    )
    route_to_reply: bool = Field(
        description="Set to true ONLY if all required info is gathered and self-validation passes."
    )
    self_validation: str = Field(
        description="If routing to reply, explain how the gathered facts definitively answer the query safely."
    )
    identified_risks: list[str] = Field(
        description="Any risks or missing data handling strategies.", default=[]
    )


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
1. **SYNTHESIS-OVER-DELEGATION (Claude Code v2.1.88 pattern):**
   - You MUST understand agent findings BEFORE creating new tasks based on them.
   - When delegating based on completed task results, your task description MUST include:
     * Specific data/facts extracted from prior tasks (no vague references like "check the results")
     * File paths, record IDs, or line numbers if the prior task returned them
     * Clear decision rationale grounded in the prior results
   - Example BAD delegation: "Check policy for the product" (vague, no context from prior tasks)
   - Example GOOD delegation: "Check discount policy for product_id=LAP-001 (150 units in stock per retriever task 1). Return allowed discount % and minimum quantity threshold."

2. **Decompose & Assign:** If you need information, output a list of `tasks`. LangGraph executes them concurrently. Keep descriptions hyper-specific, factual, and strictly objective. Do NOT include assumptions, speculative reasoning, or subjective framing.

3. **Selective Context:** Use `context_needed` to dictate exactly what the sub-agent needs (e.g. if research agent doesn't need to know the customer's name, don't inject it).

4. **Failure Handling:** If a task in the `Failed Tasks` section failed, DO NOT blindly retry it. Analyze the logic failure, adjust the query, or try a different assignee.

5. **Self-Validation Loop:** Before setting `route_to_reply=True`, you MUST verify:
   - Do the completed tasks answer the core intent?
   - Did the policy agent clear any pricing/discount requests?
   - For discount or bundle requests, did the retriever return quantity/stock/cost-aware negotiation guidance?
   - Is there any hallucinated data we must filter?

6. **Replan Limits:** You are on Replan Cycle {replan_count} of {max_replans}. If you hit the limit, you MUST set `route_to_reply=True` and draft a fallback/safe reply with what you have.

7. **Owner Mode:** If the sender is 'owner', act as their proactive business partner. Do not just answer the literal question; fan-out tasks to fetch surrounding context (like stock levels, cost prices, and active supplier contracts) so the final reply provides deep, actionable business insights.

### Few-Shot Examples
**Example 1: Initial Request needing planning**
*State:* User asking for laptop discounts.
*Output:*
{{
  "reasoning": "Need internal negotiation guidance plus policy limits before replying.",
  "tasks": [
    {{"task_id": "1", "description": "Evaluate discount request for the requested product and quantity. Return stock, selling price, internal cost-aware max discount, whether approval is required, and a customer-safe negotiation summary.", "assignee": "retriever", "priority": "required", "depends_on": [], "context_needed": ["raw_message", "sender_role"]}},
    {{"task_id": "2", "description": "Check discount and concession policy for this pricing request, including any owner-approval threshold.", "assignee": "policy", "priority": "required", "depends_on": [], "context_needed": ["sender_role"]}}
  ],
  "route_to_reply": false,
  "self_validation": "N/A",
  "identified_risks": ["Potential low stock"]
}}

**Example 2: Self-Validation (Ready to Reply)**
*State:* Completed Tasks successfully found stock and policy rules.
*Output:*
{{
  "reasoning": "Internal negotiation guidance shows a safe discount band and policy allows negotiation within that band.",
  "tasks": [],
  "route_to_reply": true,
  "self_validation": "We have facts from retriever (stock, price, safe discount band) and policy (approval threshold). Safe to negotiate without exposing internal cost.",
  "identified_risks": []
}}

### Core Business Rules
{rules_context}

### Context Envelope
- Sender: {sender_name} ({sender_role})
- Intent: {intent_label} | Urgency: {urgency_level}
- Original Message: {raw_message}
- Long-Term Preferences: {long_term_memory}
- Sender Memory Summary: {sender_memory}
- Short-Term Chat History: {short_term_memory}

### Feedback Loop States
== COMPLETED TASKS ==
{completed_tasks_text}

== FAILED / QUARANTINED TASKS ==
{failed_tasks_text}
"""


def _is_discount_request(raw_message: str) -> bool:
    text = (raw_message or "").lower()
    keywords = ("discount", "bundle", "bulk", "% off", "price", "quote")
    return any(keyword in text for keyword in keywords)


def _is_supplier_terms_request(raw_message: str, sender_role: str) -> bool:
    if (sender_role or "").lower() != "supplier":
        return False
    text = (raw_message or "").lower()
    keywords = ("payment terms", "invoice", "net 30", "net-30", "lead time", "supplier terms")
    return any(keyword in text for keyword in keywords)


def _is_policy_question(raw_message: str) -> bool:
    text = (raw_message or "").lower()
    keywords = (
        "return policy",
        "refund policy",
        "defective item",
        "defective items",
        "privacy policy",
        "data privacy",
        "supplier payment terms",
        "partner agreement",
    )
    return any(keyword in text for keyword in keywords)


def _has_task_result(completed_tasks: list[dict[str, Any]], assignee: str) -> bool:
    return any(
        task.get("assignee") == assignee and task.get("status") == "completed"
        for task in completed_tasks
    )


def orchestrator_agent(state: dict[str, Any]) -> dict[str, Any]:
    """
    Supervisor routing: runs constraint-based planning, handles replan limits,
    and maps tasks to isolated sub-agents.
    """
    # 1. State tracking & Limit Enforcement
    replan_count = state.get("replan_count", 0)
    warnings = state.get("orchestrator_warnings", [])
    raw_message = state.get("raw_message", "")
    completed_tasks = state.get("completed_tasks", [])
    sender_role = state.get("sender_role", "")

    # Reset per-run circuit breakers on the first orchestrator call of a new pipeline run
    if replan_count == 0:
        reset_circuit_breaker()
        reset_permission_denials()

    if _is_discount_request(raw_message):
        has_retriever = _has_task_result(completed_tasks, "retriever")
        has_policy = _has_task_result(completed_tasks, "policy")
        if not has_retriever or not has_policy:
            active_tasks = []
            if not has_retriever:
                active_tasks.append(
                    {
                        "task_id": "discount-retriever",
                        "description": f"Evaluate this discount request using internal negotiation guidance: '{raw_message}'. Infer product, quantity, requested discount, stock, and safe discount range. Return a customer-safe summary and whether approval is required.",
                        "assignee": "retriever",
                        "status": "pending",
                        "result": "",
                        "priority": "required",
                        "context_needed": ["raw_message", "sender_role"],
                        "depends_on": [],
                        "injected_context": {"allow_internal_tools": True},
                    }
                )
            if not has_policy:
                active_tasks.append(
                    {
                        "task_id": "discount-policy",
                        "description": f"Check pricing and discount policy for this exact request: '{raw_message}'. Determine whether the requested discount is allowed or requires owner approval.",
                        "assignee": "policy",
                        "status": "pending",
                        "result": "",
                        "priority": "required",
                        "context_needed": ["sender_role"],
                        "depends_on": [],
                    }
                )
            return {
                "active_tasks": active_tasks,
                "route_to_reply": False,
                "replan_count": replan_count + 1,
                "plan_steps": ["Deterministic discount negotiation planning path used."],
                "orchestrator_warnings": warnings,
            }
        return {
            "active_tasks": [],
            "route_to_reply": True,
            "replan_count": replan_count,
            "plan_steps": [
                "Deterministic discount negotiation path satisfied with retriever and policy results."
            ],
            "orchestrator_warnings": warnings,
        }

    if _is_supplier_terms_request(raw_message, sender_role):
        has_policy = _has_task_result(completed_tasks, "policy")
        if not has_policy:
            return {
                "active_tasks": [
                    {
                        "task_id": "supplier-policy",
                        "description": f"Check supplier terms policy for this exact request: '{raw_message}'. Return the applicable supplier payment or contract terms only from verified policy context.",
                        "assignee": "policy",
                        "status": "pending",
                        "result": "",
                        "priority": "required",
                        "context_needed": ["sender_role"],
                        "depends_on": [],
                    }
                ],
                "route_to_reply": False,
                "replan_count": replan_count + 1,
                "plan_steps": ["Deterministic supplier-terms planning path used."],
                "orchestrator_warnings": warnings,
            }
        return {
            "active_tasks": [],
            "route_to_reply": True,
            "replan_count": replan_count,
            "plan_steps": ["Deterministic supplier-terms path satisfied with policy results."],
            "orchestrator_warnings": warnings,
        }

    if _is_policy_question(raw_message):
        has_policy = _has_task_result(completed_tasks, "policy")
        if not has_policy:
            return {
                "active_tasks": [
                    {
                        "task_id": "policy-fastpath",
                        "description": f"Check policy for this exact request: '{raw_message}'. Return only verified policy guidance relevant to the sender role.",
                        "assignee": "policy",
                        "status": "pending",
                        "result": "",
                        "priority": "required",
                        "context_needed": ["sender_role"],
                        "depends_on": [],
                    }
                ],
                "route_to_reply": False,
                "replan_count": replan_count + 1,
                "plan_steps": ["Deterministic policy-question planning path used."],
                "orchestrator_warnings": warnings,
            }
        return {
            "active_tasks": [],
            "route_to_reply": True,
            "replan_count": replan_count,
            "plan_steps": ["Deterministic policy-question path satisfied with policy results."],
            "orchestrator_warnings": warnings,
        }

    # Pre-emption: If we hit loop limits, force reply
    is_exceeded, limit_msg = check_replan_limit(cast(Any, state))
    if is_exceeded:
        warnings.append(limit_msg)
        return {
            "active_tasks": [],
            "route_to_reply": True,
            "replan_count": replan_count,
            "plan_steps": ["Forced reply due to replan limit exhaustion."],
            "orchestrator_warnings": warnings,
        }

    import json

    # 2. Format Feedback Loop States
    completed_text = compress_context(completed_tasks, max_tokens=4000)

    failed_tasks = state.get("failed_tasks", [])
    failed_text = "\n".join(
        [f"Task {t['task_id']} ({t['assignee']}) FAILED: {t['result']}" for t in failed_tasks]
    )

    prompt_kwargs = {
        "sender_name": state.get("sender_name", "Unknown"),
        "sender_role": sender_role or "Unknown",
        "intent_label": state.get("intent_label", "Unknown"),
        "urgency_level": state.get("urgency_level", "Unknown"),
        "raw_message": raw_message,
        "rules_context": state.get("rules_context", ""),
        "long_term_memory": state.get("long_term_memory", ""),
        "sender_memory": state.get("sender_memory", ""),
        "short_term_memory": state.get("short_term_memory", []),
        "completed_tasks_text": completed_text if completed_text else "None yet.",
        "failed_tasks_text": failed_text if failed_text else "None.",
        "replan_count": replan_count,
        "max_replans": settings.MAX_REPLAN_CYCLES,
    }

    # 3. Call LLM Supervisor
    prompt = PromptTemplate.from_template(system_prompt_template)
    formatted_prompt = prompt.format(**prompt_kwargs)

    llm = get_chat_llm(scope="default", temperature=0.0)
    router_llm = llm.with_structured_output(OrchestratorDecision)
    decision_raw = router_llm.invoke(formatted_prompt)
    if isinstance(decision_raw, OrchestratorDecision):
        decision = decision_raw
    elif isinstance(decision_raw, dict):
        decision = OrchestratorDecision.model_validate(decision_raw)
    else:
        decision = OrchestratorDecision.model_validate(cast(Any, decision_raw).model_dump())

    # 4. Harness Constraints & Fan-Out Mapping
    active_tasks = []

    # Apply parallel task guard limit (respects settings.MAX_PARALLEL_TASKS)
    sanitized_tasks = cast(
        list[TaskDef],
        check_parallel_task_limit(cast(Any, decision.tasks), max_tasks=settings.MAX_PARALLEL_TASKS),
    )

    # Build the task DAG payload
    for t in sanitized_tasks:
        active_tasks.append(
            {
                "task_id": t.task_id,
                "description": t.description,
                "assignee": t.assignee,
                "status": "pending",
                "result": "",
                "priority": t.priority,
                "context_needed": t.context_needed,
                "depends_on": t.depends_on,
            }
        )

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
        "orchestrator_warnings": warnings,
    }
