from __future__ import annotations

import json
import re
from typing import Any

from backend.models.agent_response import AgentResponse

TaskRecord = dict[str, Any]

_APPROVAL_PREFIX = "APPROVAL RULE:"

_CONCESSION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b(special offer|special pricing|special deal)\b", re.IGNORECASE),
        "Commercial concession proposed",
    ),
    (
        re.compile(
            r"\b(waive return shipping|waive shipping|free add-on|free upgrade|free of charge)\b",
            re.IGNORECASE,
        ),
        "Fee waiver or free benefit proposed",
    ),
    (
        re.compile(r"\b(refund exception|goodwill refund|special refund)\b", re.IGNORECASE),
        "Refund exception proposed",
    ),
]

_LIABILITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(we are liable|we accept liability|this is entirely our fault)\b", re.IGNORECASE
        ),
        "Liability admission detected",
    ),
    (
        re.compile(r"\b(we guarantee|guaranteed outcome|no risk)\b", re.IGNORECASE),
        "Guarantee language detected",
    ),
]

_COMMITMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(exclusive deal|exclusivity|priority allocation|reserved inventory)\b",
            re.IGNORECASE,
        ),
        "Commercial commitment detected",
    ),
    (
        re.compile(r"\b(net[- ]?60|extended payment terms|custom payment terms)\b", re.IGNORECASE),
        "Non-standard payment commitment detected",
    ),
    (
        re.compile(r"\b(ship by|deliver by|guarantee delivery|commit to deliver)\b", re.IGNORECASE),
        "Delivery commitment detected",
    ),
]

_COMMERCIAL_FACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{1,2}%\b"), "Numeric commercial percentage stated without direct grounding"),
    (
        re.compile(r"\b\$\d+(?:\.\d{1,2})?\b"),
        "Specific commercial amount stated without direct grounding",
    ),
]

_DISCOUNT_REPLY_PATTERN = re.compile(
    r"(?:discount(?:\s+of)?\s*|offer\s*)(\d{1,2}(?:\.\d{1,2})?)\s*%|"
    r"(\d{1,2}(?:\.\d{1,2})?)\s*%\s*discount",
    re.IGNORECASE,
)
_MAX_DISCOUNT_PATTERN = re.compile(r'"max_discount_pct"\s*:\s*(\d{1,2}(?:\.\d{1,2})?)')
_APPROVAL_REQUIRED_PATTERN = re.compile(r'"approval_required"\s*:\s*(true|false)', re.IGNORECASE)


def _task_text(task: TaskRecord, key: str) -> str:
    return str(task.get(key) or "")


def _task_payload(task: TaskRecord) -> str:
    result_text = _task_text(task, "result")
    try:
        resp = AgentResponse.model_validate_json(result_text)
        return f"{resp.result} {' '.join(resp.facts)} {' '.join(resp.constraints)}"
    except Exception:
        return result_text


def _task_agent_response(task: TaskRecord) -> AgentResponse | None:
    result_text = _task_text(task, "result")
    try:
        return AgentResponse.model_validate_json(result_text)
    except Exception:
        return None


def _extract_discount_guidance(completed_tasks: list[TaskRecord]) -> dict[str, Any] | None:
    for task in completed_tasks:
        if _task_text(task, "assignee") != "retriever":
            continue
        resp = _task_agent_response(task)
        raw_text = resp.result if resp else _task_text(task, "result")
        try:
            payload = json.loads(raw_text)
            if isinstance(payload, dict) and "max_discount_pct" in payload:
                return payload
        except Exception:
            pass

        max_match = _MAX_DISCOUNT_PATTERN.search(raw_text)
        approval_match = _APPROVAL_REQUIRED_PATTERN.search(raw_text)
        if max_match:
            return {
                "max_discount_pct": float(max_match.group(1)),
                "approval_required": approval_match.group(1).lower() == "true"
                if approval_match
                else False,
            }
    return None


def _discount_negotiation_flags(reply_text: str, completed_tasks: list[TaskRecord]) -> list[str]:
    match = _DISCOUNT_REPLY_PATTERN.search(reply_text)
    if not match:
        return []

    offered_discount = float(match.group(1) or match.group(2))
    guidance = _extract_discount_guidance(completed_tasks)
    if not guidance:
        label = (
            "Bulk discount offer lacks internal negotiation guidance"
            if "bulk discount" in reply_text.lower()
            else "Commercial concession proposed"
        )
        return [f"{_APPROVAL_PREFIX} {label}"]

    max_discount = float(guidance.get("max_discount_pct", 0.0) or 0.0)
    approval_required = bool(guidance.get("approval_required", False))
    if approval_required or offered_discount > max_discount:
        return [f"{_APPROVAL_PREFIX} Discount exceeds verified negotiation range"]

    return []


def _scan_patterns(text: str, patterns: list[tuple[re.Pattern[str], str]]) -> list[str]:
    flags: list[str] = []
    for pattern, label in patterns:
        if pattern.search(text):
            flags.append(f"{_APPROVAL_PREFIX} {label}")
    return flags


def _grounding_flags(
    reply_text: str, completed_tasks: list[TaskRecord], unverified_claims: list[str]
) -> list[str]:
    flags: list[str] = []
    supporting_text = " ".join(_task_payload(task) for task in completed_tasks).lower()

    for claim in unverified_claims:
        flags.append(f"{_APPROVAL_PREFIX} Ungrounded claim reported by reply agent: {claim}")

    if not completed_tasks:
        for pattern, label in _COMMERCIAL_FACT_PATTERNS:
            if pattern.search(reply_text):
                flags.append(f"{_APPROVAL_PREFIX} {label}")
        return flags

    commercial_keywords = ("discount", "refund", "commission", "price", "shipping", "delivery")
    if (
        any(keyword in reply_text.lower() for keyword in commercial_keywords)
        and not supporting_text
    ):
        flags.append(f"{_APPROVAL_PREFIX} Commercial claim lacks retrieved evidence")

    has_policy_approval_signal = (
        "verdict:    requires_approval" in supporting_text
        or "verdict: requires_approval" in supporting_text
        or "verdict:    disallowed" in supporting_text
    )

    if has_policy_approval_signal and re.search(
        r"\b(can|will|offer|promise)\b", reply_text, re.IGNORECASE
    ):
        flags.append(
            f"{_APPROVAL_PREFIX} Reply proposes an action that retrieved evidence says requires owner approval"
        )

    return flags


def approval_rule_node(state: dict[str, Any]) -> dict[str, Any]:
    reply_text = str(state.get("reply_text", ""))
    completed_tasks = list(state.get("completed_tasks", []))
    unverified_claims = list(state.get("unverified_claims", []))

    flags: list[str] = []
    flags.extend(_discount_negotiation_flags(reply_text, completed_tasks))
    flags.extend(_scan_patterns(reply_text, _CONCESSION_PATTERNS))
    flags.extend(_scan_patterns(reply_text, _LIABILITY_PATTERNS))
    flags.extend(_scan_patterns(reply_text, _COMMITMENT_PATTERNS))
    flags.extend(_grounding_flags(reply_text, completed_tasks, unverified_claims))

    return {
        "approval_rule_flags": flags,
        "approval_rule_requires_approval": bool(flags),
    }
