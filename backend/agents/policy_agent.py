"""
Policy & Constraint Sub-Agent (PROPOSAL §4.4)

Looks up company policies regarding pricing, compliance, disclosure, etc.
Accepts a specific SubTask assigned by the Orchestrator.

## TODO
- [ ] Load RULE.md as the primary policy source
- [ ] Implement policy lookup (keyword match or semantic search over rules)
- [ ] Return structured policy result: allowed | disallowed | requires_approval
- [ ] Identify hard constraints vs soft guidelines
- [ ] Identify role-specific disclosure boundaries
- [ ] Add try/except with structured failure return
- [ ] Consider: should this agent use an LLM to interpret rules, or pure rule-matching?
"""

from backend.graph.state import SubTask

# ────────────────────────────────────────────────────────
# Prompt — used if LLM interprets policy rules
# ────────────────────────────────────────────────────────
POLICY_SYSTEM_PROMPT = """\
You are a Policy Evaluator. Your ONLY job is to check company rules and
return what is allowed, disallowed, or requires approval.

### Instructions
- Given the policy question below, search the provided rules.
- Return a structured answer:
  - `allowed` — the action is permitted by policy
  - `disallowed` — the action violates a hard constraint (cite which rule)
  - `requires_approval` — the action needs owner sign-off before proceeding
  - `no_rule_found` — no existing policy covers this situation
- Do NOT invent policies. If no rule exists, say so.
- Do NOT soften hard constraints.

### Company Rules
{rules_context}

### Policy Question
{task_description}

### Sender Role
{sender_role}
"""


def policy_agent(task: SubTask) -> dict:
    """
    Execute the specific policy lookup instructions.

    Input:  SubTask dict from Orchestrator fan-out
    Output: dict with 'completed_tasks' list to merge back to main state

    Functions needed (implement later):
    - _load_rules() -> str                         # Load RULE.md content
    - _search_rules(query, rules_text) -> list[str] # Find relevant rule sections
    - _evaluate_policy(query, matched_rules, sender_role) -> PolicyResult
    """
    # TODO: Replace stub with real policy lookup
    completed_task = task.copy()
    completed_task["status"] = "completed"
    completed_task["result"] = f"(Stub) Policy rules found for: {task['description']}"

    return {"completed_tasks": [completed_task]}
