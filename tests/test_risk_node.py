"""
Risk Node Tests — verify correct risk classification.
"""

import pytest

from backend.nodes.risk import (
    risk_node,
    _scan_for_risky_keywords,
    _check_disclosure,
    _check_escalation_triggers,
    _check_policy_cross,
    _check_unverified_claims,
    _aggregate_risk,
)


# ── Structure / Contract ──────────────────────────────────────

class TestRiskNodeStructure:
    """Ensure the node always returns the expected state keys."""

    def test_returns_required_keys(self):
        state = {"reply_text": "Hello!", "sender_role": "customer"}
        result = risk_node(state)
        assert "risk_level" in result
        assert "risk_flags" in result
        assert "requires_approval" in result
        assert result["risk_level"] in ("low", "medium", "high")
        assert isinstance(result["risk_flags"], list)
        assert isinstance(result["requires_approval"], bool)

    def test_handles_empty_state(self):
        result = risk_node({})
        assert result["risk_level"] == "low"
        assert result["risk_flags"] == []
        assert result["requires_approval"] is False


# ── Low Risk (auto-send) ─────────────────────────────────────

class TestLowRisk:
    """Safe replies should pass through with no flags."""

    def test_simple_greeting(self):
        state = {"reply_text": "Thank you for reaching out! How can I help?", "sender_role": "customer"}
        result = risk_node(state)
        assert result["risk_level"] == "low"
        assert result["requires_approval"] is False
        assert result["risk_flags"] == []

    def test_informational_reply(self):
        state = {
            "reply_text": "Our store hours are 9 AM to 5 PM, Monday through Friday.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["risk_level"] == "low"
        assert result["requires_approval"] is False


# ── Price Commitment Flags ────────────────────────────────────

class TestPriceCommitments:
    """Replies containing price promises should be flagged."""

    def test_price_match_promise(self):
        state = {
            "reply_text": "We can do a price match for you on that order.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["risk_level"] in ("medium", "high")
        assert result["requires_approval"] is True
        assert any("price match" in f.lower() for f in result["risk_flags"])

    def test_bulk_discount_offer(self):
        state = {
            "reply_text": "I can offer a bulk discount of 20% on orders over 100 units.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("bulk discount" in f.lower() for f in result["risk_flags"])

    def test_refund_promise(self):
        state = {
            "reply_text": "We will refund the full amount to your account.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("refund" in f.lower() for f in result["risk_flags"])

    def test_free_of_charge(self):
        state = {
            "reply_text": "We will replace it free of charge.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["requires_approval"] is True

    def test_special_offer(self):
        state = {
            "reply_text": "I have a special offer for your next order.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["requires_approval"] is True


# ── Delivery / Stock Guarantees ───────────────────────────────

class TestDeliveryGuarantees:
    """Unverified delivery or stock claims should be flagged."""

    def test_delivery_guarantee(self):
        state = {
            "reply_text": "We guarantee delivery within 3 business days.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("delivery" in f.lower() for f in result["risk_flags"])

    def test_ship_by_date(self):
        state = {
            "reply_text": "We will ship by Friday.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["requires_approval"] is True

    def test_in_stock_claim_no_confirmation(self):
        state = {
            "reply_text": "That item is currently in stock.",
            "sender_role": "customer",
            "completed_tasks": [],
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("stock" in f.lower() for f in result["risk_flags"])

    def test_in_stock_claim_with_retriever_confirmation(self):
        """If retriever confirmed stock, the unverified-claim flag should not fire."""
        state = {
            "reply_text": "That item is currently in stock.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "1",
                    "assignee": "retriever",
                    "status": "completed",
                    "result": "Product X — stock level: 42 units available in inventory.",
                    "description": "Check stock for Product X",
                }
            ],
        }
        result = risk_node(state)
        # The stock unverified claim flag should NOT be present
        unverified = [f for f in result["risk_flags"] if "unverified stock" in f.lower()]
        assert unverified == []


# ── Escalation Triggers (always HIGH) ─────────────────────────

class TestEscalationTriggers:
    """Escalation language must always produce risk_level=high."""

    @pytest.mark.parametrize(
        "text",
        [
            "We are aware of the pending lawsuit and are taking it seriously.",
            "This constitutes a breach of contract under clause 4.",
            "There is a physical safety hazard with this product batch.",
            "We have received the cease and desist notice.",
            "A regulatory violation has been identified during the audit.",
            "We are initiating a product recall for batch #42.",
        ],
    )
    def test_escalation_phrases(self, text):
        state = {"reply_text": text, "sender_role": "customer"}
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True
        assert any(f.startswith("ESCALATION:") for f in result["risk_flags"])


# ── Confidentiality Violations ────────────────────────────────

class TestConfidentiality:
    """Internal financial data must never leak to customers or suppliers."""

    def test_margin_leak_to_customer(self):
        state = {
            "reply_text": "Our profit margin on this product is 35%.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True
        assert any("CONFIDENTIALITY" in f for f in result["risk_flags"])

    def test_cost_price_leak_to_supplier(self):
        state = {
            "reply_text": "The unit cost from our other supplier is $2.50.",
            "sender_role": "supplier",
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True

    def test_margin_ok_for_investor(self):
        """Investors are allowed to see financial metrics."""
        state = {
            "reply_text": "Our profit margin on this product is 35%.",
            "sender_role": "investor",
        }
        result = risk_node(state)
        confidentiality_flags = [f for f in result["risk_flags"] if "CONFIDENTIALITY" in f]
        assert confidentiality_flags == []

    def test_margin_ok_for_owner(self):
        """Owner should see everything."""
        state = {
            "reply_text": "Our gross margin is 42% and the cost price is $12.",
            "sender_role": "owner",
        }
        result = risk_node(state)
        confidentiality_flags = [f for f in result["risk_flags"] if "CONFIDENTIALITY" in f]
        assert confidentiality_flags == []

    def test_source_code_leak_to_customer(self):
        state = {
            "reply_text": "You can find the source code in our repository.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert any("CONFIDENTIALITY" in f for f in result["risk_flags"])

    def test_api_key_leak(self):
        state = {
            "reply_text": "Here is the API key for the integration.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert any("CONFIDENTIALITY" in f for f in result["risk_flags"])


# ── Policy Cross-Check ────────────────────────────────────────

class TestPolicyCrossCheck:
    """If a policy agent marked something 'disallowed', the reply should be flagged."""

    def test_disallowed_policy(self):
        state = {
            "reply_text": "Sure, we can do that.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "p1",
                    "assignee": "policy",
                    "status": "completed",
                    "result": "disallowed — bulk discounts over 15% violate pricing rule §3",
                    "description": "Can we offer 25% bulk discount?",
                }
            ],
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert any("POLICY VIOLATION" in f for f in result["risk_flags"])

    def test_allowed_policy_no_flag(self):
        state = {
            "reply_text": "Sure, we can do that.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "p1",
                    "assignee": "policy",
                    "status": "completed",
                    "result": "allowed — 10% discount is within policy",
                    "description": "Can we offer 10% discount?",
                }
            ],
        }
        result = risk_node(state)
        policy_flags = [f for f in result["risk_flags"] if "POLICY VIOLATION" in f]
        assert policy_flags == []


# ── Aggregation Logic ─────────────────────────────────────────

class TestAggregation:
    """Verify the _aggregate_risk scoring logic directly."""

    def test_no_flags_is_low(self):
        assert _aggregate_risk([]) == ("low", False)

    def test_single_medium_flag(self):
        level, approval = _aggregate_risk(["Price match promise detected — requires policy verification"])
        assert level == "medium"
        assert approval is True

    def test_escalation_flag_is_high(self):
        level, approval = _aggregate_risk(["ESCALATION: Legal action language detected"])
        assert level == "high"
        assert approval is True

    def test_confidentiality_flag_is_high(self):
        level, approval = _aggregate_risk(["CONFIDENTIALITY: Internal margin disclosure to customer — blocked by policy"])
        assert level == "high"
        assert approval is True

    def test_three_medium_flags_escalate_to_high(self):
        flags = [
            "Price match promise detected — requires policy verification",
            "Bulk discount offer detected — requires policy verification",
            "Delivery guarantee detected — must be confirmed by retriever agent",
        ]
        level, approval = _aggregate_risk(flags)
        assert level == "high"
        assert approval is True

    def test_two_medium_flags_stay_medium(self):
        flags = [
            "Price match promise detected — requires policy verification",
            "Delivery guarantee detected — must be confirmed by retriever agent",
        ]
        level, approval = _aggregate_risk(flags)
        assert level == "medium"
        assert approval is True


# ── Combined / Integration ────────────────────────────────────

class TestCombinedScenarios:
    """End-to-end scenarios with multiple risk signals."""

    def test_price_and_escalation_combined(self):
        state = {
            "reply_text": "We can do a price match, but note the breach of contract issue.",
            "sender_role": "customer",
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True
        assert len(result["risk_flags"]) >= 2

    def test_safe_reply_to_investor(self):
        state = {
            "reply_text": (
                "Our gross margin this quarter is 38%. Revenue grew 12% YoY. "
                "We'd love to schedule a call to walk through the full financials."
            ),
            "sender_role": "investor",
        }
        result = risk_node(state)
        # Investor is allowed to see margins — should be low risk
        assert result["risk_level"] == "low"
        assert result["requires_approval"] is False
