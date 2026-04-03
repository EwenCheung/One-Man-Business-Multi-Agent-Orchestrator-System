"""
Risk Rules — Rule-Based Evaluation Layer

Implements the deterministic Layer 1 checkers and the aggregation logic
for the risk node.  No LLM calls here — all logic is regex / keyword /
heuristic, so this module is fast, cheap, and fully testable without
any API keys or network access.

Checkers:
    1. Price commitment keywords    (price match, bulk discount, refund promises)
    2. Delivery / stock guarantee patterns
    3. Escalation triggers          (legal action, safety, contract breach, recall)
    4. Confidentiality violations   (margins/costs leaked to wrong roles)
    5. Policy cross-check           (DISALLOWED / REQUIRES_APPROVAL verdicts)
    6. Unverified claim cross-reference (reply vs retriever results)
    7. Confidence signals           (high/medium/low + unverified_claims)
    8. Tone anomaly flags           (over-committed, speculative, etc.)
    9. Intent + urgency context     (complaint/legal/critical)
   10. PII / sensitive data leakage (credit card, SSN, passport, password)
   11. Role-based sensitivity       (tighter thresholds for customer-facing replies)

Aggregation:
    _aggregate_risk() maps collected flags → (risk_level, requires_approval).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.models.agent_response import AgentResponse

logger = logging.getLogger(__name__)

TaskRecord = dict[str, Any]

# ── Keyword / Pattern Definitions ──────────────────────────────

# Patterns that indicate risky price commitments or guarantees
_PRICE_COMMITMENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\bprice\s*match", re.IGNORECASE),
        "Price match promise detected — requires policy verification",
    ),
    (
        re.compile(r"\bguarantee[ds]?\s+(price|cost|rate|fee)", re.IGNORECASE),
        "Price guarantee detected — requires policy verification",
    ),
    (
        re.compile(r"\bwe\s+will\s+(refund|compensate|reimburse)", re.IGNORECASE),
        "Refund/compensation promise detected — requires approval",
    ),
    (
        re.compile(r"\bfree\s+of\s+charge\b", re.IGNORECASE),
        "Free-of-charge commitment detected — requires approval",
    ),
]

# Patterns indicating unverified delivery/stock promises
_DELIVERY_GUARANTEE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\bguarantee[ds]?\s+(delivery|shipping|dispatch)", re.IGNORECASE),
        "Delivery guarantee detected — must be confirmed by retriever agent",
    ),
    (
        re.compile(r"\b(ship|deliver|dispatch)\s+(by|before|within)\s+\w+", re.IGNORECASE),
        "Specific delivery timeline detected — must be confirmed by retriever agent",
    ),
]

# Escalation trigger patterns — always flag as HIGH
_ESCALATION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\b(lawsuit|legal\s*action|litigation|sue|court\s*order)", re.IGNORECASE),
        "ESCALATION: Legal action language detected",
    ),
    (
        re.compile(r"\bbreach\s*(of\s*)?(contract|agreement|terms|NDA)", re.IGNORECASE),
        "ESCALATION: Contract breach language detected",
    ),
    (
        re.compile(r"\b(physical\s*safety|injury|harm|danger|hazard|unsafe)", re.IGNORECASE),
        "ESCALATION: Safety concern language detected",
    ),
    (
        re.compile(
            r"\b(regulatory\s*violation|compliance\s*breach|audit\s*finding)", re.IGNORECASE
        ),
        "ESCALATION: Regulatory violation language detected",
    ),
    (
        re.compile(r"\b(cease\s*and\s*desist|subpoena|injunction)", re.IGNORECASE),
        "ESCALATION: Legal instrument language detected",
    ),
    (
        re.compile(r"\b(recall|product\s*defect)", re.IGNORECASE),
        "ESCALATION: Product recall/defect language detected",
    ),
]

# Confidential terms that should never be disclosed to certain roles
_CONFIDENTIAL_TERMS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\b(profit\s*margin|gross\s*margin|net\s*margin|markup)", re.IGNORECASE),
        "Internal margin disclosure",
    ),
    (
        re.compile(
            r"\b(cost\s*price|unit\s*cost|wholesale\s*cost|landed\s*cost|cogs)\b", re.IGNORECASE
        ),
        "Internal cost disclosure",
    ),
    (
        re.compile(r"\b(internal\s*pricing|our\s*cost|we\s*pay)\b", re.IGNORECASE),
        "Internal pricing disclosure",
    ),
    (
        re.compile(r"\b(source\s*code|codebase|repository|api\s*key|secret\s*key)", re.IGNORECASE),
        "Technical asset disclosure",
    ),
]

# Roles that must NEVER receive confidential financial information
_CONFIDENTIAL_BLOCKED_ROLES = {"customer", "supplier", "unknown"}

_HIGH_RISK_INTENTS = {"complaint", "legal", "escalation", "dispute", "refund", "chargeback"}
_CRITICAL_URGENCY = {"critical"}

# ── PII / Sensitive Data Patterns ─────────────────────────────────
# Any match in the outgoing reply is an IMMEDIATE HIGH risk → hold.
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Credit / debit card numbers (Visa, MC, Amex, Discover)
    (
        re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "PII: Credit card number pattern detected in reply",
    ),
    # US Social Security Number (SSN)
    (
        re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
        "PII: US Social Security Number (SSN) pattern detected in reply",
    ),
    # Passport-like numeric block (crude match gated on context word)
    (
        re.compile(r"\b(passport|national\s*id)\s*[:#]?\s*[A-Z0-9]{6,12}\b", re.IGNORECASE),
        "PII: Passport/National ID reference detected in reply",
    ),
    # API / secret keys (common formats: sk-, pk-, AKIA…)
    (
        re.compile(r"\b(sk-[A-Za-z0-9]{20,}|pk-[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b"),
        "PII: API/Secret key pattern detected in reply",
    ),
    # Password literal disclosure
    (
        re.compile(r"\b(password|passwd|secret)\s*[:=]\s*\S{6,}", re.IGNORECASE),
        "PII: Password/secret literal detected in reply",
    ),
    # Bank account number (rough: 8-17 digit block near 'account' or 'IBAN')
    (
        re.compile(
            r"\b(?:account\s*(?:no|number|#)?\s*[:.]?\s*\d{8,17}|IBAN\s*(?:is\s+)?[:#]?\s*[A-Z]{2}\d{2}[A-Z0-9]{10,30})\b",
            re.IGNORECASE,
        ),
        "PII: Bank account / IBAN reference detected in reply",
    ),
]

# ── Role-Based Sensitivity Config ─────────────────────────────────
# Maps role → extra flags that should auto-trigger a MEDIUM risk even
# when other pattern checkers are clean.
_ROLE_SENSITIVE_PHRASES: dict[str, list[tuple[re.Pattern, str]]] = {
    "customer": [
        (
            re.compile(
                r"\b(internal|confidential|proprietary|not\s+for\s+distribution)\b", re.IGNORECASE
            ),
            "ROLE RISK: Confidential/internal language surfaced in customer-facing reply",
        ),
        (
            re.compile(r"\b(our\s+supplier|supplier\s+name|vendor\s+name)\b", re.IGNORECASE),
            "ROLE RISK: Supplier identity potentially exposed to customer",
        ),
    ],
    "partner": [
        (
            re.compile(r"\b(profit\s+share|equity|ownership\s+stake|dilution)\b", re.IGNORECASE),
            "ROLE RISK: Equity/profit-share language in partner reply — verify before sending",
        ),
    ],
    "investor": [
        (
            re.compile(r"\b(guaranteed\s+return|assured\s+profit|no\s+risk)\b", re.IGNORECASE),
            "ROLE RISK: Misleading investment guarantee language detected",
        ),
    ],
}

_LOW_CONFIDENCE_KEYWORDS = {
    "low confidence",
    "could not confirm",
    "unable to verify",
    "hedged",
    "not explicitly confirmed",
    "follow up",
    "follow-up",
    "unable to confirm",
    "not confirmed",
    "not verified",
}

_HIGH_RISK_TONE_FLAGS = {"over-committed", "speculative"}
_MEDIUM_RISK_TONE_FLAGS = {"over-apologetic", "defensive"}

_ESCALATION_PREFIX = "ESCALATION:"
_CONFIDENTIALITY_PREFIX = "CONFIDENTIALITY:"
_POLICY_PREFIX = "POLICY VIOLATION:"
_POLICY_APPROVAL_PREFIX = "POLICY REQUIRES APPROVAL:"
_CONFIDENCE_LOW_PREFIX = "LOW CONFIDENCE:"
_TONE_HIGH_PREFIX = "TONE HIGH RISK:"
_PII_PREFIX = "PII:"
_ROLE_RISK_PREFIX = "ROLE RISK:"


# ── Helper Functions ───────────────────────────────────────────


def _normalize_text(value: str | None) -> str:
    """Return a lowercase, stripped string for defensive comparisons."""
    return (value or "").lower().strip()


def _task_text(task: TaskRecord, key: str) -> str:
    """Safely extract a string field from a task record."""
    return str(task.get(key) or "")


def _has_retriever_confirmation(
    completed_tasks: list[TaskRecord], keywords: tuple[str, ...]
) -> bool:
    """Check whether any retriever task confirms one of the supplied keywords."""
    for task in completed_tasks:
        if _task_text(task, "assignee") != "retriever":
            continue
        if _task_text(task, "status") != "completed":
            continue

        result_text = _task_text(task, "result")
        search_text = result_text
        try:
            resp = AgentResponse.model_validate_json(result_text)
            search_text = " ".join(resp.facts) if resp.facts else resp.result
        except Exception:
            pass

        search_text = _normalize_text(search_text)
        if any(keyword in search_text for keyword in keywords):
            return True
    return False


def format_completed_tasks_summary(completed_tasks: list[TaskRecord]) -> str:
    """Build a compact task summary for the LLM reviewer."""
    if not completed_tasks:
        return "No sub-agent results."

    task_lines = []
    for task in completed_tasks:
        result_text = _task_text(task, "result")
        try:
            resp = AgentResponse.model_validate_json(result_text)
            display_result = f"[Status: {resp.status}, Confidence: {resp.confidence}] {resp.result}"
        except Exception:
            display_result = result_text

        task_lines.append(
            f"[{_task_text(task, 'assignee').upper() or '?'}] {_task_text(task, 'description')}: "
            f"{display_result[:300]}"
        )

    return "\n".join(task_lines)


def format_existing_flags(flags: list[str]) -> str:
    """Render existing rule-based flags for the LLM second pass."""
    if not flags:
        return "None"
    return "\n".join(f"- {flag}" for flag in flags)


def _extract_policy_signals(result_text: str) -> tuple[bool, bool, bool]:
    """Return disallowed / requires-approval / hard-constraint booleans."""
    normalized = _normalize_text(result_text)
    has_disallowed = "verdict:    disallowed" in normalized or (
        normalized.startswith("disallowed") and "verdict:" not in normalized
    )
    has_requires_approval = "verdict:    requires_approval" in normalized
    has_hard_constraint = "hard constraint: yes" in normalized
    return has_disallowed, has_requires_approval, has_hard_constraint


# ── Rule-Based Checkers ─────────────────────────────────────────


def _scan_patterns(text: str, patterns: list[tuple[re.Pattern, str]]) -> list[str]:
    """Run a list of (compiled_regex, flag_message) against *text*."""
    flags = []
    for pattern, message in patterns:
        if pattern.search(text):
            flags.append(message)
    return flags


def scan_for_risky_keywords(reply_text: str) -> list[str]:
    """Check reply for price commitments, delivery guarantees, and other risky phrases."""
    flags = []
    flags.extend(_scan_patterns(reply_text, _PRICE_COMMITMENT_PATTERNS))
    flags.extend(_scan_patterns(reply_text, _DELIVERY_GUARANTEE_PATTERNS))
    return flags


def check_disclosure(reply_text: str, sender_role: str) -> list[str]:
    """Ensure no internal margins/costs leak to roles that shouldn't see them."""
    if _normalize_text(sender_role) not in _CONFIDENTIAL_BLOCKED_ROLES:
        return []

    flags = []
    for pattern, label in _CONFIDENTIAL_TERMS:
        if pattern.search(reply_text):
            flags.append(f"CONFIDENTIALITY: {label} to {sender_role} — blocked by policy")
    return flags


def check_escalation_triggers(reply_text: str) -> list[str]:
    """Detect language that requires immediate owner intervention."""
    return _scan_patterns(reply_text, _ESCALATION_PATTERNS)


def check_policy_cross(completed_tasks: list[TaskRecord]) -> list[str]:
    """Cross-check reply against policy-agent findings.

    Catches three policy-agent signals:
      - verdict = DISALLOWED        → hard policy violation
      - verdict = REQUIRES_APPROVAL → owner must sign off
      - hard_constraint = YES       → non-overridable rule breached
    """
    flags: list[str] = []
    for task in completed_tasks:
        if _task_text(task, "assignee") != "policy":
            continue

        task_ref = f"task {task.get('task_id', '?')} — '{_task_text(task, 'description')}'"
        result_text = _task_text(task, "result")
        has_hard_constraint = False

        try:
            resp = AgentResponse.model_validate_json(result_text)
            scan_text = resp.result
            if any("HARD CONSTRAINT" in c for c in resp.constraints):
                has_hard_constraint = True
        except Exception:
            scan_text = result_text

        has_disallowed, has_requires_approval, fallback_hc = _extract_policy_signals(scan_text)
        has_hard_constraint = has_hard_constraint or fallback_hc

        if has_disallowed:
            flags.append(f"POLICY VIOLATION: Policy disallowed action in {task_ref}")

        elif has_requires_approval:
            flags.append(f"POLICY REQUIRES APPROVAL: Owner sign-off needed per {task_ref}")

        if has_hard_constraint:
            flags.append(f"POLICY VIOLATION: Hard constraint breached in {task_ref}")
    return flags


def check_unverified_claims(reply_text: str, completed_tasks: list[TaskRecord]) -> list[str]:
    """Flag delivery/stock claims that lack a successful retriever confirmation."""
    has_stock_confirmation = _has_retriever_confirmation(completed_tasks, ("stock", "inventory"))
    has_delivery_confirmation = _has_retriever_confirmation(completed_tasks, ("deliver", "ship"))

    flags = []
    if re.search(r"\bin\s+stock\b", reply_text, re.IGNORECASE) and not has_stock_confirmation:
        flags.append("Unverified stock claim — no retriever confirmation found")
    if (
        re.search(r"\b(ship|deliver|dispatch)\s+(by|before|within)", reply_text, re.IGNORECASE)
        and not has_delivery_confirmation
    ):
        flags.append("Unverified delivery timeline — no retriever confirmation found")
    return flags


def check_confidence(
    confidence_level: str, confidence_note: str, unverified_claims: list[str]
) -> list[str]:
    """Flag low-confidence replies that may contain unverified information.

    Reads three sources:
      - confidence_level: machine-readable field from ReplyOutput ('high'|'medium'|'low')
      - confidence_note:  human-readable note for keyword fallback
      - unverified_claims: self-reported hedged statements from the reply agent
    """
    flags: list[str] = []
    normalized_level = _normalize_text(confidence_level)

    if normalized_level == "low":
        flags.append(
            "LOW CONFIDENCE: Reply agent reported low confidence — significant gaps in verified information"
        )
    elif normalized_level == "medium":
        flags.append(
            "MEDIUM CONFIDENCE: Reply agent reported medium confidence — some claims may be hedged"
        )
    elif not normalized_level:  # Fallback: keyword scan on confidence_note
        note_lower = _normalize_text(confidence_note)
        if any(keyword in note_lower for keyword in _LOW_CONFIDENCE_KEYWORDS):
            flags.append("MEDIUM CONFIDENCE: Confidence note indicates unverified claims in reply")

    for claim in unverified_claims:
        flags.append(f"UNVERIFIED CLAIM: {claim}")

    return flags


def check_tone(tone_flags: list[str]) -> list[str]:
    """Translate tone anomalies self-reported by the reply agent into risk flags.

    High-risk tones (over-committed, speculative) escalate to HIGH.
    Medium-risk tones (over-apologetic, defensive) escalate to MEDIUM.
    """
    flags: list[str] = []
    for tone in tone_flags:
        tone_lower = _normalize_text(tone)
        if tone_lower in _HIGH_RISK_TONE_FLAGS:
            flags.append(
                f"TONE HIGH RISK: {tone} — reply may imply unverified commitments or unfounded projections"
            )
        elif tone_lower in _MEDIUM_RISK_TONE_FLAGS:
            flags.append(f"TONE MEDIUM RISK: {tone} — reply tone may escalate or imply liability")
    return flags


def check_intent_urgency(intent_label: str, urgency_level: str) -> list[str]:
    """Lower the risk threshold when the message context is inherently sensitive.

    - Legal/complaint intents warrant extra scrutiny even on benign-looking replies.
    - Critical urgency indicates time pressure that increases risk of rushed mistakes.
    """
    flags: list[str] = []
    if _normalize_text(intent_label) in _HIGH_RISK_INTENTS:
        flags.append(
            f"CONTEXT: High-risk intent '{intent_label}' — reply requires additional scrutiny"
        )
    if _normalize_text(urgency_level) in _CRITICAL_URGENCY:
        flags.append(
            "CONTEXT: Critical urgency — time pressure increases risk of unverified commitments"
        )
    return flags


def check_pii_leakage(reply_text: str) -> list[str]:
    """Scan the outgoing reply for PII / sensitive credential patterns.

    Any match triggers an immediate HIGH risk hold — the reply must never
    be auto-delivered if it contains account numbers, card numbers, SSNs,
    API keys, or password literals.
    """
    return _scan_patterns(reply_text, _PII_PATTERNS)


def check_role_sensitivity(reply_text: str, sender_role: str) -> list[str]:
    """Apply role-specific phrase sensitivity checks.

    Certain language is acceptable in some contexts but dangerous when surfaced
    to the wrong audience.  For example, mentioning our supplier's identity to a
    customer should always be flagged for review.

    Args:
        reply_text: The draft reply text.
        sender_role: Normalised role of the message recipient.

    Returns:
        A list of ``ROLE RISK: …`` flag strings.
    """
    normalized_role = _normalize_text(sender_role)
    role_patterns = _ROLE_SENSITIVE_PHRASES.get(normalized_role, [])
    return _scan_patterns(reply_text, role_patterns)


# ── Risk Aggregation ───────────────────────────────────────────


def aggregate_risk(flags: list[str]) -> tuple[str, bool]:
    """
    Score the collected flags and decide approval requirements.
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
    has_confidence_low = any(f.startswith(_CONFIDENCE_LOW_PREFIX) for f in flags)
    has_tone_high = any(f.startswith(_TONE_HIGH_PREFIX) for f in flags)
    has_pii = any(f.startswith(_PII_PREFIX) for f in flags)
    has_role_risk = any(f.startswith(_ROLE_RISK_PREFIX) for f in flags)

    # PII / sensitive credential leak → always HIGH regardless of other flags
    if has_pii:
        return ("high", True)

    # Escalation, confidentiality leaks, or policy violations → always HIGH
    if has_escalation or has_confidentiality or has_policy_violation:
        return ("high", True)

    # Low-confidence reply or high-risk tone → HIGH
    if has_confidence_low or has_tone_high:
        return ("high", True)

    # Policy requires-approval → at least MEDIUM
    if has_policy_approval:
        return ("medium", True)

    # Role-based sensitivity flags → medium (reviewable, not necessarily blocked)
    if has_role_risk:
        return ("medium", True)

    # Multiple medium-severity flags → treat as high
    if len(flags) >= 3:
        return ("high", True)

    # Any remaining flags → medium
    return ("medium", True)
