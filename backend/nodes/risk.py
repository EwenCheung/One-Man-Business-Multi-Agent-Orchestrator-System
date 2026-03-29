"""
Risk Node (PROPOSAL §4.7) — Rule-Based, No LLM

Aggregates risk signals and decides whether the reply can be sent
or must be held for owner approval.

Scans:
    1. Risky keyword patterns (price promises, guarantees, legal terms)
    2. Confidentiality violations (margins/costs leaked to wrong roles)
    3. Escalation triggers (legal action, safety, contract breach)
    4. Policy cross-check (reply contradicts policy-agent findings)

Scoring:
    - Any escalation trigger → HIGH (auto-hold)
    - Any confidentiality violation → HIGH (auto-hold)
    - ≥2 medium-severity flags → HIGH
    - ≥1 medium-severity flag → MEDIUM (hold for review)
    - 0 flags → LOW (auto-send)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Keyword / Pattern Definitions ──────────────────────────────

# Patterns that indicate risky price commitments or guarantees
_PRICE_COMMITMENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bprice\s*match", re.IGNORECASE),
     "Price match promise detected — requires policy verification"),
    (re.compile(r"\bbulk\s*discount", re.IGNORECASE),
     "Bulk discount offer detected — requires policy verification"),
    (re.compile(r"\bguarantee[ds]?\s+(price|cost|rate|fee)", re.IGNORECASE),
     "Price guarantee detected — requires policy verification"),
    (re.compile(r"\bspecial\s*(offer|pricing|rate|deal)", re.IGNORECASE),
     "Special pricing offer detected — requires policy verification"),
    (re.compile(r"\bwe\s+will\s+(refund|compensate|reimburse)", re.IGNORECASE),
     "Refund/compensation promise detected — requires approval"),
    (re.compile(r"\bfree\s+of\s+charge\b", re.IGNORECASE),
     "Free-of-charge commitment detected — requires approval"),
]

# Patterns indicating unverified delivery/stock promises
_DELIVERY_GUARANTEE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bguarantee[ds]?\s+(delivery|shipping|dispatch)", re.IGNORECASE),
     "Delivery guarantee detected — must be confirmed by retriever agent"),
    (re.compile(r"\b(ship|deliver|dispatch)\s+(by|before|within)\s+\w+", re.IGNORECASE),
     "Specific delivery timeline detected — must be confirmed by retriever agent"),
    (re.compile(r"\bin\s+stock\b", re.IGNORECASE),
     "Stock availability claim detected — must be confirmed by retriever agent"),
]

# Escalation trigger patterns — always flag as HIGH
_ESCALATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(lawsuit|legal\s*action|litigation|sue|court\s*order)", re.IGNORECASE),
     "ESCALATION: Legal action language detected"),
    (re.compile(r"\bbreach\s*(of\s*)?(contract|agreement|terms|NDA)", re.IGNORECASE),
     "ESCALATION: Contract breach language detected"),
    (re.compile(r"\b(physical\s*safety|injury|harm|danger|hazard|unsafe)", re.IGNORECASE),
     "ESCALATION: Safety concern language detected"),
    (re.compile(r"\b(regulatory\s*violation|compliance\s*breach|audit\s*finding)", re.IGNORECASE),
     "ESCALATION: Regulatory violation language detected"),
    (re.compile(r"\b(cease\s*and\s*desist|subpoena|injunction)", re.IGNORECASE),
     "ESCALATION: Legal instrument language detected"),
    (re.compile(r"\b(recall|product\s*defect)", re.IGNORECASE),
     "ESCALATION: Product recall/defect language detected"),
]

# Confidential terms that should never be disclosed to certain roles
_CONFIDENTIAL_TERMS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(profit\s*margin|gross\s*margin|net\s*margin|markup)", re.IGNORECASE),
     "Internal margin disclosure"),
    (re.compile(r"\b(cost\s*price|unit\s*cost|wholesale\s*cost|landed\s*cost|cogs)\b", re.IGNORECASE),
     "Internal cost disclosure"),
    (re.compile(r"\b(internal\s*pricing|our\s*cost|we\s*pay)\b", re.IGNORECASE),
     "Internal pricing disclosure"),
    (re.compile(r"\b(source\s*code|codebase|repository|api\s*key|secret\s*key)", re.IGNORECASE),
     "Technical asset disclosure"),
]

# Roles that must NEVER receive confidential financial information
_CONFIDENTIAL_BLOCKED_ROLES = {"customer", "supplier", "unknown"}


def _scan_patterns(text: str, patterns: list[tuple[re.Pattern, str]]) -> list[str]:
    """Run a list of (compiled_regex, flag_message) against *text*."""
    flags = []
    for pattern, message in patterns:
        if pattern.search(text):
            flags.append(message)
    return flags


def _scan_for_risky_keywords(reply_text: str) -> list[str]:
    """Check reply for price commitments, delivery guarantees, and other risky phrases."""
    flags = []
    flags.extend(_scan_patterns(reply_text, _PRICE_COMMITMENT_PATTERNS))
    flags.extend(_scan_patterns(reply_text, _DELIVERY_GUARANTEE_PATTERNS))
    return flags


def _check_disclosure(reply_text: str, sender_role: str) -> list[str]:
    """Ensure no internal margins/costs leak to roles that shouldn't see them."""
    if sender_role.lower() not in _CONFIDENTIAL_BLOCKED_ROLES:
        return []

    flags = []
    for pattern, label in _CONFIDENTIAL_TERMS:
        if pattern.search(reply_text):
            flags.append(
                f"CONFIDENTIALITY: {label} to {sender_role} — blocked by policy"
            )
    return flags


def _check_escalation_triggers(reply_text: str) -> list[str]:
    """Detect language that requires immediate owner intervention."""
    return _scan_patterns(reply_text, _ESCALATION_PATTERNS)


def _check_policy_cross(completed_tasks: list[dict[str, Any]]) -> list[str]:
    """Cross-check reply against policy-agent findings.

    Catches three policy-agent signals:
      - verdict = DISALLOWED        → hard policy violation
      - verdict = REQUIRES_APPROVAL → owner must sign off
      - hard_constraint = YES       → non-overridable rule breached
    """
    flags: list[str] = []
    for task in completed_tasks:
        if task.get("assignee") != "policy":
            continue
        result_text = (task.get("result") or "").lower()
        task_ref = f"task {task.get('task_id', '?')} — '{task.get('description', '')}'"

        has_disallowed = (
            "verdict:    disallowed" in result_text
            or (result_text.startswith("disallowed") and "verdict:" not in result_text)
        )
        has_requires_approval = "verdict:    requires_approval" in result_text

        if has_disallowed:
            flags.append(f"POLICY VIOLATION: Policy disallowed action in {task_ref}")

        elif has_requires_approval:
            flags.append(
                f"POLICY REQUIRES APPROVAL: Owner sign-off needed per {task_ref}"
            )

        if "hard constraint: yes" in result_text:
            flags.append(
                f"POLICY VIOLATION: Hard constraint breached in {task_ref}"
            )
    return flags


def _check_unverified_claims(reply_text: str, completed_tasks: list[dict[str, Any]]) -> list[str]:
    """Flag delivery/stock claims that lack a successful retriever confirmation."""
    has_stock_confirmation = any(
        t.get("assignee") == "retriever"
        and t.get("status") == "completed"
        and ("stock" in (t.get("result") or "").lower()
             or "inventory" in (t.get("result") or "").lower())
        for t in completed_tasks
    )
    has_delivery_confirmation = any(
        t.get("assignee") == "retriever"
        and t.get("status") == "completed"
        and ("deliver" in (t.get("result") or "").lower()
             or "ship" in (t.get("result") or "").lower())
        for t in completed_tasks
    )

    flags = []
    if re.search(r"\bin\s+stock\b", reply_text, re.IGNORECASE) and not has_stock_confirmation:
        flags.append("Unverified stock claim — no retriever confirmation found")
    if re.search(r"\b(ship|deliver|dispatch)\s+(by|before|within)", reply_text, re.IGNORECASE) and not has_delivery_confirmation:
        flags.append("Unverified delivery timeline — no retriever confirmation found")
    return flags


# ── Risk Aggregation ───────────────────────────────────────────

_ESCALATION_PREFIX = "ESCALATION:"
_CONFIDENTIALITY_PREFIX = "CONFIDENTIALITY:"
_POLICY_PREFIX = "POLICY VIOLATION:"
_POLICY_APPROVAL_PREFIX = "POLICY REQUIRES APPROVAL:"


def _aggregate_risk(flags: list[str]) -> tuple[str, bool]:
    """
    Score the collected flags and decide approval requirements.

    Returns:
        (risk_level, requires_approval)
        - "high"   + True  → auto-hold, owner must approve
        - "medium" + True  → hold for owner review
        - "low"    + False → safe to send automatically
    """
    if not flags:
        return ("low", False)

    has_escalation = any(f.startswith(_ESCALATION_PREFIX) for f in flags)
    has_confidentiality = any(f.startswith(_CONFIDENTIALITY_PREFIX) for f in flags)
    has_policy_violation = any(f.startswith(_POLICY_PREFIX) for f in flags)
    has_policy_approval = any(f.startswith(_POLICY_APPROVAL_PREFIX) for f in flags)

    # Escalation, confidentiality leaks, or policy violations → always HIGH
    if has_escalation or has_confidentiality or has_policy_violation:
        return ("high", True)

    # Policy requires-approval → at least MEDIUM
    if has_policy_approval:
        return ("medium", True)

    # Multiple medium-severity flags → treat as high
    if len(flags) >= 3:
        return ("high", True)

    # Any remaining flags → medium
    return ("medium", True)


def risk_node(state: dict) -> dict:
    """
    Evaluate risk of the generated reply and decide approval requirements.

    Reads from state:
        - reply_text         (str)  — candidate reply from the Reply Agent
        - sender_role        (str)  — who we are replying to
        - completed_tasks    (list) — sub-agent results for cross-checking

    Writes to state:
        - risk_level         ("low" | "medium" | "high")
        - risk_flags         (list[str]) — human-readable reasons
        - requires_approval  (bool)
    """
    reply_text: str = state.get("reply_text", "")
    sender_role: str = state.get("sender_role", "unknown")
    completed_tasks: list[dict[str, Any]] = state.get("completed_tasks", [])

    flags = []
    flags.extend(_scan_for_risky_keywords(reply_text))
    flags.extend(_check_disclosure(reply_text, sender_role))
    flags.extend(_check_escalation_triggers(reply_text))
    flags.extend(_check_policy_cross(completed_tasks))
    flags.extend(_check_unverified_claims(reply_text, completed_tasks))

    risk_level, requires_approval = _aggregate_risk(flags)

    logger.info(
        "Risk evaluation complete — level=%s, flags=%d, approval=%s",
        risk_level, len(flags), requires_approval,
    )
    for flag in flags:
        logger.info("  risk_flag: %s", flag)

    return {
        "risk_level": risk_level,
        "risk_flags": flags,
        "requires_approval": requires_approval,
    }
