"""
Risk Node Tests — verify correct risk classification.
"""

from unittest.mock import MagicMock, patch
import os

import pytest

from backend.nodes.risk import risk_node
from backend.nodes.risk_llm import RiskJudgement, llm_second_pass
from backend.nodes.risk_rules import (
    aggregate_risk,
    check_confidence,
    check_intent_urgency,
    check_tone,
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

    def test_disallowed_policy_old_format(self):
        """Backward compat: plain 'disallowed' substring still triggers."""
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

    def test_disallowed_policy_structured_format(self):
        """New format: _format_result produces 'Verdict:    DISALLOWED'."""
        state = {
            "reply_text": "Sure, we can do that.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "p1",
                    "assignee": "policy",
                    "status": "completed",
                    "result": (
                        "Verdict:    DISALLOWED\n"
                        "Confidence: HIGH\n"
                        "Hard Constraint: NO\n\n"
                        "Explanation:\nBulk discounts over 15% violate pricing rule §3."
                    ),
                    "description": "Can we offer 25% bulk discount?",
                }
            ],
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert any("POLICY VIOLATION" in f for f in result["risk_flags"])

    def test_requires_approval_policy(self):
        """Policy verdict REQUIRES_APPROVAL should flag for owner sign-off."""
        state = {
            "reply_text": "We can look into that for you.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "p2",
                    "assignee": "policy",
                    "status": "completed",
                    "result": (
                        "Verdict:    REQUIRES_APPROVAL\n"
                        "Confidence: MEDIUM\n"
                        "Hard Constraint: NO\n\n"
                        "Explanation:\nCustom pricing requires owner approval."
                    ),
                    "description": "Can we offer custom pricing?",
                }
            ],
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("POLICY REQUIRES APPROVAL" in f for f in result["risk_flags"])

    def test_hard_constraint_flag(self):
        """Hard constraint = YES should always trigger a POLICY VIOLATION."""
        state = {
            "reply_text": "We can share that information.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "p3",
                    "assignee": "policy",
                    "status": "completed",
                    "result": (
                        "Verdict:    DISALLOWED\n"
                        "Confidence: HIGH\n"
                        "Hard Constraint: YES\n\n"
                        "Explanation:\nSharing supplier cost data with customers is a hard constraint."
                    ),
                    "description": "Can we share supplier cost breakdown?",
                }
            ],
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        # Should have both a disallowed flag and a hard constraint flag
        assert sum("POLICY VIOLATION" in f for f in result["risk_flags"]) >= 2

    def test_allowed_policy_no_flag(self):
        state = {
            "reply_text": "Sure, we can do that.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "p1",
                    "assignee": "policy",
                    "status": "completed",
                    "result": (
                        "Verdict:    ALLOWED\n"
                        "Confidence: HIGH\n"
                        "Hard Constraint: NO\n\n"
                        "Explanation:\n10% discount is within policy."
                    ),
                    "description": "Can we offer 10% discount?",
                }
            ],
        }
        result = risk_node(state)
        policy_flags = [f for f in result["risk_flags"] if "POLICY" in f]
        assert policy_flags == []

    def test_not_covered_policy_no_flag(self):
        """Verdict NOT_COVERED should not flag — absence of rules isn't a violation."""
        state = {
            "reply_text": "Let me check on that.",
            "sender_role": "customer",
            "completed_tasks": [
                {
                    "task_id": "p4",
                    "assignee": "policy",
                    "status": "completed",
                    "result": (
                        "Verdict:    NOT_COVERED\n"
                        "Confidence: LOW\n"
                        "Hard Constraint: NO\n\n"
                        "Explanation:\nNo existing policy covers this situation."
                    ),
                    "description": "Can we do X?",
                }
            ],
        }
        result = risk_node(state)
        policy_flags = [f for f in result["risk_flags"] if "POLICY" in f]
        assert policy_flags == []


# ── Aggregation Logic ─────────────────────────────────────────

class TestAggregation:
    """Verify the _aggregate_risk scoring logic directly."""

    def test_no_flags_is_low(self):
        assert aggregate_risk([]) == ("low", False)

    def test_single_medium_flag(self):
        level, approval = aggregate_risk(["Price match promise detected — requires policy verification"])
        assert level == "medium"
        assert approval is True

    def test_escalation_flag_is_high(self):
        level, approval = aggregate_risk(["ESCALATION: Legal action language detected"])
        assert level == "high"
        assert approval is True

    def test_confidentiality_flag_is_high(self):
        level, approval = aggregate_risk(["CONFIDENTIALITY: Internal margin disclosure to customer — blocked by policy"])
        assert level == "high"
        assert approval is True

    def test_three_medium_flags_escalate_to_high(self):
        flags = [
            "Price match promise detected — requires policy verification",
            "Bulk discount offer detected — requires policy verification",
            "Delivery guarantee detected — must be confirmed by retriever agent",
        ]
        level, approval = aggregate_risk(flags)
        assert level == "high"
        assert approval is True

    def test_two_medium_flags_stay_medium(self):
        flags = [
            "Price match promise detected — requires policy verification",
            "Delivery guarantee detected — must be confirmed by retriever agent",
        ]
        level, approval = aggregate_risk(flags)
        assert level == "medium"
        assert approval is True

    def test_policy_requires_approval_is_medium(self):
        level, approval = aggregate_risk(["POLICY REQUIRES APPROVAL: Owner sign-off needed per task p2"])
        assert level == "medium"
        assert approval is True

    def test_policy_violation_is_high(self):
        level, approval = aggregate_risk(["POLICY VIOLATION: Policy disallowed action in task p1"])
        assert level == "high"
        assert approval is True

    def test_low_confidence_is_high(self):
        level, approval = aggregate_risk(["LOW CONFIDENCE: Reply agent reported low confidence — significant gaps"])
        assert level == "high"
        assert approval is True

    def test_tone_high_risk_is_high(self):
        level, approval = aggregate_risk(["TONE HIGH RISK: over-committed — reply may imply unverified commitments"])
        assert level == "high"
        assert approval is True


# ── Confidence-Based Auto-Hold (Idea 6) ──────────────────────

class TestConfidenceBased:
    """Confidence level and unverified claims from the reply agent should feed risk."""

    def test_low_confidence_level_is_high_risk(self):
        state = {
            "reply_text": "We can sort that out for you.",
            "sender_role": "customer",
            "confidence_level": "low",
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True
        assert any("LOW CONFIDENCE" in f for f in result["risk_flags"])

    def test_medium_confidence_level_is_medium_risk(self):
        state = {
            "reply_text": "We can sort that out for you.",
            "sender_role": "customer",
            "confidence_level": "medium",
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("MEDIUM CONFIDENCE" in f for f in result["risk_flags"])

    def test_high_confidence_level_no_flag(self):
        state = {
            "reply_text": "Here are your order details.",
            "sender_role": "customer",
            "confidence_level": "high",
        }
        result = risk_node(state)
        confidence_flags = [f for f in result["risk_flags"] if "CONFIDENCE" in f]
        assert confidence_flags == []

    def test_unverified_claims_are_flagged(self):
        state = {
            "reply_text": "We will ship by Friday.",
            "sender_role": "customer",
            "confidence_level": "medium",
            "unverified_claims": ["ships by Friday — not confirmed by retriever"],
        }
        result = risk_node(state)
        assert any("UNVERIFIED CLAIM" in f for f in result["risk_flags"])

    def test_confidence_note_keyword_fallback(self):
        """If confidence_level is absent, keyword scan on confidence_note fires."""
        state = {
            "reply_text": "We can look into that.",
            "sender_role": "customer",
            "confidence_level": "",
            "confidence_note": "Medium confidence — stock not explicitly confirmed; reply hedged accordingly.",
        }
        result = risk_node(state)
        assert any("MEDIUM CONFIDENCE" in f for f in result["risk_flags"])

    def test_check_confidence_direct_low(self):
        flags = check_confidence("low", "", [])
        assert any("LOW CONFIDENCE" in f for f in flags)

    def test_check_confidence_direct_medium(self):
        flags = check_confidence("medium", "", [])
        assert any("MEDIUM CONFIDENCE" in f for f in flags)

    def test_check_confidence_direct_high_no_flags(self):
        flags = check_confidence("high", "", [])
        assert flags == []

    def test_check_confidence_unverified_claims(self):
        flags = check_confidence("high", "", ["price quoted — not verified by policy agent"])
        assert any("UNVERIFIED CLAIM" in f for f in flags)


# ── Tone Analysis (Idea 2) ────────────────────────────────────

class TestToneAnalysis:
    """Tone flags self-reported by the reply agent should raise risk level."""

    def test_over_committed_is_high_risk(self):
        state = {
            "reply_text": "We will sort everything out.",
            "sender_role": "customer",
            "tone_flags": ["over-committed"],
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert result["requires_approval"] is True
        assert any("TONE HIGH RISK" in f for f in result["risk_flags"])

    def test_speculative_is_high_risk(self):
        state = {
            "reply_text": "We expect to have that resolved soon.",
            "sender_role": "customer",
            "tone_flags": ["speculative"],
        }
        result = risk_node(state)
        assert result["risk_level"] == "high"
        assert any("TONE HIGH RISK" in f for f in result["risk_flags"])

    def test_over_apologetic_is_medium_risk(self):
        state = {
            "reply_text": "We are so sorry for this.",
            "sender_role": "customer",
            "tone_flags": ["over-apologetic"],
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("TONE MEDIUM RISK" in f for f in result["risk_flags"])

    def test_defensive_is_medium_risk(self):
        state = {
            "reply_text": "This is not our fault.",
            "sender_role": "customer",
            "tone_flags": ["defensive"],
        }
        result = risk_node(state)
        assert result["requires_approval"] is True
        assert any("TONE MEDIUM RISK" in f for f in result["risk_flags"])

    def test_no_tone_flags_no_tone_risk(self):
        state = {
            "reply_text": "Thank you for reaching out.",
            "sender_role": "customer",
            "tone_flags": [],
        }
        result = risk_node(state)
        tone_flags = [f for f in result["risk_flags"] if "TONE" in f]
        assert tone_flags == []

    def test_check_tone_direct(self):
        flags = check_tone(["over-committed", "defensive"])
        assert any("TONE HIGH RISK" in f for f in flags)
        assert any("TONE MEDIUM RISK" in f for f in flags)


# ── Intent + Urgency Sensitivity (Idea 8 context) ────────────

class TestIntentUrgency:
    """High-risk intents and critical urgency should add context flags."""

    @pytest.mark.parametrize("intent", ["complaint", "legal", "escalation", "dispute", "refund", "chargeback"])
    def test_high_risk_intent_flagged(self, intent):
        state = {
            "reply_text": "Thank you for your message.",
            "sender_role": "customer",
            "intent_label": intent,
            "urgency_level": "normal",
        }
        result = risk_node(state)
        assert any("CONTEXT" in f for f in result["risk_flags"])

    def test_critical_urgency_flagged(self):
        state = {
            "reply_text": "Thank you for your message.",
            "sender_role": "customer",
            "intent_label": "inquiry",
            "urgency_level": "critical",
        }
        result = risk_node(state)
        assert any("CONTEXT" in f and "urgency" in f.lower() for f in result["risk_flags"])

    def test_normal_intent_and_urgency_no_context_flag(self):
        state = {
            "reply_text": "Thank you for your message.",
            "sender_role": "customer",
            "intent_label": "inquiry",
            "urgency_level": "normal",
        }
        result = risk_node(state)
        context_flags = [f for f in result["risk_flags"] if "CONTEXT" in f]
        assert context_flags == []

    def test_check_intent_urgency_direct(self):
        flags = check_intent_urgency("complaint", "critical")
        assert len(flags) == 2
        assert any("complaint" in f for f in flags)
        assert any("urgency" in f.lower() for f in flags)


# ── Combined / Integration ────────────────────────────────────

# ── LLM Second Pass ────────────────────────────────────

class TestLLMSecondPass:
    """LLM second pass fires only for MEDIUM results and can revise the level."""

    _PATCH = "backend.utils.llm_provider.get_chat_llm"

    def _mock_llm(self, mock_get_llm, additional_flags, revised_risk_level, reasoning="OK."):
        """Wire mock_get_llm to return a mock LLM that produces a RiskJudgement."""
        judgement = RiskJudgement(
            additional_flags=additional_flags,
            revised_risk_level=revised_risk_level,
            reasoning=reasoning,
        )
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.invoke.return_value = judgement
        mock_get_llm.return_value = mock_llm

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_adds_flags(self, mock_get_llm):
        self._mock_llm(
            mock_get_llm,
            additional_flags=["IMPLIED COMMITMENT: 'I'll make it right' implies a refund"],
            revised_risk_level="medium",
        )
        additional, revised = llm_second_pass(
            reply_text="I'll make it right for you.",
            sender_role="customer",
            intent_label="complaint",
            urgency_level="normal",
            completed_tasks=[],
            existing_flags=["TONE MEDIUM RISK: over-apologetic"],
            current_level="medium",
        )
        assert any("IMPLIED COMMITMENT" in f for f in additional)
        assert revised == "medium"

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_flags_prefixed_with_llm(self, mock_get_llm):
        self._mock_llm(
            mock_get_llm,
            additional_flags=["IMPLIED COMMITMENT: 'this will be resolved'"],
            revised_risk_level="medium",
        )
        additional, _ = llm_second_pass("x", "customer", "complaint", "normal", [], [], "medium")
        assert all(f.startswith("LLM:") for f in additional)

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_upgrades_to_high(self, mock_get_llm):
        self._mock_llm(
            mock_get_llm,
            additional_flags=["FACTUAL CONTRADICTION: claims same-day delivery not confirmed"],
            revised_risk_level="high",
            reasoning="Contradiction warrants HIGH.",
        )
        additional, revised = llm_second_pass(
            reply_text="We can deliver today.",
            sender_role="customer",
            intent_label="inquiry",
            urgency_level="normal",
            completed_tasks=[],
            existing_flags=["Unverified delivery timeline"],
            current_level="medium",
        )
        assert revised == "high"
        assert len(additional) == 1

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_downgrades_to_low(self, mock_get_llm):
        self._mock_llm(
            mock_get_llm,
            additional_flags=[],
            revised_risk_level="low",
            reasoning="Rule-based flag was a false positive; reply is safe.",
        )
        additional, revised = llm_second_pass(
            reply_text="Thank you for your order.",
            sender_role="customer",
            intent_label="inquiry",
            urgency_level="normal",
            completed_tasks=[],
            existing_flags=["TONE MEDIUM RISK: over-apologetic"],
            current_level="medium",
        )
        assert additional == []
        assert revised == "low"

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_llm_failure_falls_back(self, mock_get_llm):
        mock_get_llm.side_effect = RuntimeError("API timeout")
        additional, revised = llm_second_pass(
            reply_text="Thank you.",
            sender_role="customer",
            intent_label="inquiry",
            urgency_level="normal",
            completed_tasks=[],
            existing_flags=[],
            current_level="medium",
        )
        assert additional == []
        assert revised == "medium"

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_invalid_level_falls_back_to_current(self, mock_get_llm):
        self._mock_llm(
            mock_get_llm,
            additional_flags=[],
            revised_risk_level="NONSENSE",
        )
        _, revised = llm_second_pass("x", "customer", "inquiry", "normal", [], [], "medium")
        assert revised == "medium"

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_risk_node_medium_triggers_llm_pass(self, mock_get_llm):
        """Integration: a MEDIUM rule-based result calls the LLM second pass."""
        self._mock_llm(
            mock_get_llm,
            additional_flags=["IMPLIED COMMITMENT: 'We'll sort this out' is an implicit promise"],
            revised_risk_level="high",
            reasoning="Implicit promise warrants upgrade to HIGH.",
        )
        state = {
            "reply_text": "We'll sort this out for you.",
            "sender_role": "customer",
            "tone_flags": ["over-apologetic"],  # 1 flag → MEDIUM from rule-based
        }
        result = risk_node(state)
        mock_get_llm.assert_called_once()
        assert result["risk_level"] == "high"
        assert any("LLM:" in f for f in result["risk_flags"])

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_risk_node_high_skips_llm_pass(self, mock_get_llm):
        """Integration: a HIGH rule-based result does not call the LLM second pass."""
        state = {
            "reply_text": "There is a physical safety hazard with this product.",
            "sender_role": "customer",
        }
        risk_node(state)
        mock_get_llm.assert_not_called()

    @patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
    @patch("backend.utils.llm_provider.get_chat_llm")
    def test_risk_node_low_skips_llm_pass(self, mock_get_llm):
        """Integration: a LOW rule-based result does not call the LLM second pass."""
        state = {
            "reply_text": "Thank you for your message. We will be in touch.",
            "sender_role": "customer",
        }
        risk_node(state)
        mock_get_llm.assert_not_called()


# ── Combined Scenarios ──────────────────────────────────

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
