"""
Risk Node (PROPOSAL §4.7) — Rule-Based, No LLM

Aggregates risk signals and decides whether the reply can be sent
or must be held for owner approval.

## TODO
- [ ] Keyword scan: check reply_text for risky patterns (price promises, legal terms, etc.)
- [ ] Policy cross-check: verify reply doesn't violate constraints from completed policy tasks
- [ ] Confidentiality check: ensure no internal margins/costs leak to wrong roles
- [ ] Escalation triggers: legal action, contract breach, safety → auto-hold
- [ ] Score risk as low / medium / high
- [ ] Set requires_approval = True for medium/high
- [ ] Collect risk_flags with human-readable reasons
- [ ] Make risk evaluation reproducible (log exactly why each flag was set)

Functions needed:
- _scan_for_risky_keywords(reply_text) -> list[str]
- _check_disclosure(reply_text, sender_role) -> list[str]
- _check_escalation_triggers(reply_text) -> list[str]
- _aggregate_risk(flags) -> (risk_level, requires_approval)
"""


def risk_node(state: dict) -> dict:
    """
    Evaluate risk and decide approval requirements.

    Reads from state:
        - reply_text
        - sender_role
        - completed_tasks (for policy constraint cross-check)

    Writes to state:
        - risk_level       ("low" | "medium" | "high")
        - requires_approval
        - risk_flags
    """
    # TODO: Replace with real rule-based risk checks
    # Temporary pass-through so the pipeline doesn't crash
    return {
        "risk_level": "low",
        "risk_flags": [],
        "requires_approval": False,
    }
