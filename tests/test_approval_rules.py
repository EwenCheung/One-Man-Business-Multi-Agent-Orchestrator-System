import json

import pytest

from backend.models.agent_response import AgentResponse
from backend.nodes.approval_rules import approval_rule_node


def _make_discount_task(max_discount_pct: float, approval_required: bool = False) -> dict:
    """Build a completed retriever task with a properly serialised AgentResponse."""
    inner_result = json.dumps(
        {
            "max_discount_pct": max_discount_pct,
            "recommended_discount_pct": max_discount_pct,
            "approval_required": approval_required,
        }
    )
    result_json = AgentResponse(
        status="success",
        confidence="high",
        result=inner_result,
        facts=[],
        unknowns=[],
        constraints=[],
    ).model_dump_json()
    return {
        "task_id": "1",
        "assignee": "retriever",
        "status": "completed",
        "result": result_json,
        "description": "Evaluate discount request",
    }

def test_discount_and_waiver_trigger_approval_rules():
    result = approval_rule_node(
        {
            "reply_text": "I can offer a custom 20% discount and waive return shipping for this order.",
            "completed_tasks": [],
            "unverified_claims": [],
        }
    )
    assert result["approval_rule_requires_approval"] is True
    assert any("Commercial concession" in flag for flag in result["approval_rule_flags"])
    assert any("Fee waiver" in flag for flag in result["approval_rule_flags"])


def test_liability_and_commitment_trigger_approval_rules():
    result = approval_rule_node(
        {
            "reply_text": "We accept liability and guarantee delivery by Friday.",
            "completed_tasks": [],
            "unverified_claims": [],
        }
    )
    assert result["approval_rule_requires_approval"] is True
    assert any("Liability admission" in flag for flag in result["approval_rule_flags"])
    assert any(
        "Guarantee language" in flag or "Delivery commitment" in flag
        for flag in result["approval_rule_flags"]
    )


def test_unverified_claims_trigger_grounding_flags():
    result = approval_rule_node(
        {
            "reply_text": "I can confirm a 12% discount.",
            "completed_tasks": [],
            "unverified_claims": ["12% discount not verified by policy agent"],
        }
    )
    assert result["approval_rule_requires_approval"] is True
    assert any("Ungrounded claim" in flag for flag in result["approval_rule_flags"])


def test_verified_in_band_discount_does_not_trigger_approval():
    result = approval_rule_node(
        {
            "reply_text": "I can offer a 10% discount for a 20-unit bundle.",
            "completed_tasks": [_make_discount_task(max_discount_pct=10.0)],
            "unverified_claims": [],
        }
    )
    assert result["approval_rule_requires_approval"] is False


def test_out_of_band_discount_triggers_approval():
    result = approval_rule_node(
        {
            "reply_text": "I can offer a 20% discount for this order.",
            "completed_tasks": [_make_discount_task(max_discount_pct=10.0)],
            "unverified_claims": [],
        }
    )
    assert result["approval_rule_requires_approval"] is True
    assert any(
        "exceeds verified negotiation range" in flag.lower()
        for flag in result["approval_rule_flags"]
    )
