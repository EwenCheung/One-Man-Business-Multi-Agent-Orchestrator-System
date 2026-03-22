"""
Orchestrator Supervisor Agent (Section 7.4)

The Supervisor of the Multi-Agent architecture.
Assigns specific tasks to sub-agents (retriever, policy, research)
and evaluates their aggregated results.
"""

from typing import Literal, List
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from backend.config import settings


class TaskDef(BaseModel):
    task_id: str = Field(description="Unique ID for this task (e.g. '1', '2')")
    description: str = Field(description="Specific instructions for the sub-agent.")
    assignee: Literal["retriever", "research", "policy", "memory"] = Field(description="The agent to execute this task.")


class OrchestratorDecision(BaseModel):
    """The structured output schema required from the Supervisor LLM."""
    reasoning: str = Field(description="Why these tasks are needed or why we are ready to reply.")
    tasks: List[TaskDef] = Field(description="List of tasks to fan-out to sub-agents. Empty if routing to reply.", default=[])
    route_to_reply: bool = Field(description="True ONLY if all needed info is in completed_tasks and we can safely reply.")


system_prompt_template = """
You are the Supervisor Orchestrator. You manage sub-agents by assigning them specific tasks.
Instead of doing the work yourself or reading the raw message to reply, you must delegate instructions to experts.

### Your Sub-Agents
1. `retriever` : Fetches internal SQL data, business documents, or supplier contracts.
2. `research` : Fetches external web searches or competitor comparisons.
3. `policy` : Looks up company rules regarding pricing, negotiations, etc.
4. `memory` : Searches specific past conversation logs, dates, or old chat histories.

### How to behave
- If you need information, output a list of `tasks`. LangGraph will execute them concurrently.
- Make the task descriptions highly specific!
- Once Sub-Agents return their results, you will be invoked again to review them.
- If the `Completed Tasks` section has all the answers you need, set `route_to_reply=True` and `tasks=[]`.

### Examples

**Example 1: Initial request requiring parallel tasks**
*State:* Customer asks "Can I get a discount on 50 laptops?"
*Output:*
{{
  "reasoning": "I need to check our current stock and pricing for laptops, and also look up our bulk discount policy.",
  "tasks": [
    {{"task_id": "1", "description": "Fetch stock and base pricing for laptops.", "assignee": "retriever"}},
    {{"task_id": "2", "description": "Look up discount policy for orders of 50+ items.", "assignee": "policy"}}
  ],
  "route_to_reply": false
}}

**Example 2: External research required**
*State:* Partner asks "How does our product compare to Competitor X's latest release?"
*Output:*
{{
  "reasoning": "I need to find out what Competitor X recently released.",
  "tasks": [
    {{"task_id": "1", "description": "Search the web for Competitor X's latest feature release.", "assignee": "research"}}
  ],
  "route_to_reply": false
}}

**Example 3: Ready to reply**
*State:* Tasks 1 and 2 are in 'Completed Tasks So Far' and contain the stock and policy info. No more further information needed and ready to reply.
*Output:*
{{
  "reasoning": "I have the stock information and the bulk discount policy from the completed tasks. I can now safely draft a reply.",
  "tasks": [],
  "route_to_reply": true
}}

### Core Business Rules
{rules_context}

### Memory & Context
- Long-Term Preferences: {long_term_memory}
- Short-Term Chat History: {short_term_memory}

### Current Message State
- Sender Name: {sender_name}
- Sender Role: {sender_role}
- Intent: {intent_label}
- Urgency: {urgency_level}
- Original Message: {raw_message}

### Completed Tasks So Far
{completed_tasks_text}
"""


def orchestrator_agent(state: dict) -> dict:
    """
    Supervisor routing: map sub-tasks to agents.
    """
    # 1. Format completed tasks for the prompt
    completed_tasks = state.get("completed_tasks", [])
    completed_text = "\n".join([f"Task {t['task_id']} ({t['assignee']}): {t['result']}" for t in completed_tasks])

    prompt_kwargs = {
        "sender_name": state.get("sender_name", "Unknown"),
        "sender_role": state.get("sender_role", "Unknown"),
        "intent_label": state.get("intent_label", "Unknown"),
        "urgency_level": state.get("urgency_level", "Unknown"),
        "raw_message": state.get("raw_message", ""),
        "rules_context": state.get("rules_context", ""),
        "long_term_memory": state.get("long_term_memory", ""),
        "short_term_memory": state.get("short_term_memory", []),
        "completed_tasks_text": completed_text if completed_text else "None yet."
    }

    # 2. Format the prompt and run LLM
    prompt = PromptTemplate.from_template(system_prompt_template)
    formatted_prompt = prompt.format(**prompt_kwargs)

    llm = ChatOpenAI(
        api_key=settings.LLM_API_KEY, 
        model=settings.LLM_MODEL, 
        temperature=0.0
    )
    router_llm = llm.with_structured_output(OrchestratorDecision)
    decision: OrchestratorDecision = router_llm.invoke(formatted_prompt)

    # 3. Handle fan-out task mapping
    active_tasks = []
    for t in decision.tasks:
        active_tasks.append({
            "task_id": t.task_id,
            "description": t.description,
            "assignee": t.assignee,
            "status": "pending",
            "result": ""
        })

    step_log = f"Reasoning: {decision.reasoning} -> Assigned {len(active_tasks)} tasks. Routing to reply: {decision.route_to_reply}"

    # 4. Return new state (plan_steps aggregates automatically)
    return {
        "active_tasks": active_tasks,
        "route_to_reply": decision.route_to_reply,
        "plan_steps": [step_log],
    }