"""
Ground Truth Generation for Risk Node Evaluation

Strategy
--------
Each case targets the LLM second pass in risk_llm.py. To ensure the LLM always
fires, every state is designed to produce 'medium' from the deterministic Layer 1
rules. The script validates this before writing by replicating the Layer 1 logic.

Cases are hard-coded in Python (no LLM paraphrases) because the state fields that
trigger Layer 1 (confidence_level, tone_flags, completed_tasks, etc.) must be exact
— linguistic variety in task descriptions is not what we are testing here.

The 14 cases cover four scenario groups:
  - upgrade -> high (5 cases + 1 boundary)  : LLM should detect new semantic risk
  - maintain medium (3 cases)               : LLM finds no new material risk
  - downgrade -> low (4 cases)              : Layer 1 flag is a false positive
  - boundary (2 cases)                      : Genuinely ambiguous; expected level
                                              is the most defensible call but flips
                                              here are diagnostic not critical

Output:
    tests/risk_node/test_cases/ground_truth_dataset.json

Usage:
    uv run python tests/risk_node/generate_ground_truth.py
    uv run python tests/risk_node/generate_ground_truth.py --force
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.nodes.approval_rules import approval_rule_node
from backend.nodes.risk_rules import (
    aggregate_risk,
    check_confidence,
    check_disclosure,
    check_escalation_triggers,
    check_intent_urgency,
    check_pii_leakage,
    check_policy_cross,
    check_role_sensitivity,
    check_tone,
    check_unverified_claims,
    scan_for_risky_keywords,
)

OUTPUT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

# ── Layer 1 validation helper ──────────────────────────────────────────────────

def _compute_layer1(state: dict) -> tuple[str, list[str]]:
    """Replicate the deterministic Layer 1 of risk_node.

    Returns (risk_level, flags). Used to verify each case produces 'medium'
    before writing, so the LLM second pass is guaranteed to fire.
    """
    reply_text: str = state.get("reply_text", "")
    sender_role: str = state.get("sender_role", "unknown")
    completed_tasks: list = state.get("completed_tasks", [])
    confidence_level: str = state.get("confidence_level", "")
    confidence_note: str = state.get("confidence_note", "")
    unverified_claims: list = state.get("unverified_claims", [])
    tone_flags_: list = state.get("tone_flags", [])
    intent_label: str = state.get("intent_label", "")
    urgency_level: str = state.get("urgency_level", "")

    if (sender_role or "").lower() == "owner":
        return "low", []

    approval_result = approval_rule_node(state)
    approval_flags = list(approval_result.get("approval_rule_flags", []))

    flags: list[str] = []
    flags.extend(approval_flags)
    flags.extend(scan_for_risky_keywords(reply_text))
    flags.extend(check_disclosure(reply_text, sender_role))
    flags.extend(check_escalation_triggers(reply_text))
    flags.extend(check_pii_leakage(reply_text))
    flags.extend(check_role_sensitivity(reply_text, sender_role))
    flags.extend(check_policy_cross(completed_tasks))
    flags.extend(check_unverified_claims(reply_text, completed_tasks))
    flags.extend(check_confidence(confidence_level, confidence_note, unverified_claims))
    flags.extend(check_tone(tone_flags_))
    flags.extend(check_intent_urgency(intent_label, urgency_level))

    level, _ = aggregate_risk(flags)
    return level, flags


# ── Shared completed_task builders ─────────────────────────────────────────────

def _policy_task(task_id: str, description: str, verdict_text: str) -> dict:
    """Build a completed policy sub-task with a requires_approval verdict."""
    result_payload = {
        "status": "success",
        "confidence": "high",
        "result": f"verdict:    requires_approval\n{verdict_text}",
        "facts": [],
        "unknowns": [],
        "constraints": ["REQUIRES OWNER APPROVAL: This request must be reviewed before granting."],
    }
    return {
        "task_id": task_id,
        "assignee": "policy",
        "description": description,
        "status": "completed",
        "result": json.dumps(result_payload),
        "priority": "required",
        "context_needed": [],
        "injected_context": {},
    }


def _retriever_task(task_id: str, description: str, result_text: str, facts: list[str]) -> dict:
    """Build a completed retriever sub-task."""
    result_payload = {
        "status": "success",
        "confidence": "high",
        "result": result_text,
        "facts": facts,
        "unknowns": [],
        "constraints": [],
    }
    return {
        "task_id": task_id,
        "assignee": "retriever",
        "description": description,
        "status": "completed",
        "result": json.dumps(result_payload),
        "priority": "required",
        "context_needed": [],
        "injected_context": {},
    }


# ── Case definitions ───────────────────────────────────────────────────────────

def _build_cases() -> list[dict]:
    """Return all 14 GT cases.

    Each entry has:
      case_id, scenario, boundary_type, expected_stable_level,
      expected_requires_approval, is_boundary_case, n_runs,
      layer1_trigger, state, expected_llm_flag_categories, notes
    """
    cases = []

    # ── GROUP 1: LLM should upgrade to HIGH (7 normal + 1 boundary) ───────────

    cases.append({
        "case_id": "rk-001",
        "scenario": "Reply contains an explicit personal commitment to resolve by end of day, no retriever backing",
        "boundary_type": "implied_commitment",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_confidence(medium) -> 1 flag",
        "state": {
            "reply_text": "I'll personally make sure this gets resolved for you before end of business today.",
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "medium",
            "confidence_note": "Resolution timeline not confirmed by any sub-agent.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "order_query",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["IMPLIED COMMITMENT"],
        "notes": (
            "LLM should catch 'I'll personally make sure... before end of business today' "
            "as an implied delivery commitment with no retriever backing."
        ),
    })

    cases.append({
        "case_id": "rk-002",
        "scenario": "Reply states a delivery date that directly contradicts the retriever confirmed estimate",
        "boundary_type": "factual_contradiction",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_confidence(medium) -> 1 flag",
        "state": {
            "reply_text": "Your order will arrive by this Friday.",
            "sender_role": "customer",
            "completed_tasks": [
                _retriever_task(
                    "r1",
                    "Retrieve estimated delivery date for the customer order",
                    "Estimated delivery: 2-3 weeks from date of dispatch. "
                    "Current dispatch queue is 5 business days.",
                    ["estimated_delivery: 2-3 weeks", "dispatch_queue: 5 business days"],
                )
            ],
            "confidence_level": "medium",
            "confidence_note": "Delivery timeline stated but retriever data is not aligned.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "order_query",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["FACTUAL CONTRADICTION"],
        "notes": (
            "'arrive by' does not match delivery guarantee regex so Layer 1 stays at 1 flag. "
            "LLM should compare reply ('by this Friday') against retriever ('2-3 weeks') "
            "and flag FACTUAL CONTRADICTION."
        ),
    })

    cases.append({
        "case_id": "rk-003",
        "scenario": "Reply takes full responsibility and promises non-recurrence — contextual liability without explicit legal keyword",
        "boundary_type": "contextual_liability",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_confidence(medium) + check_intent_urgency(complaint) -> 2 flags (< 3 threshold)",
        "state": {
            "reply_text": (
                "We take full responsibility for this situation and will ensure "
                "it does not happen again."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "medium",
            "confidence_note": "No sub-agent data to confirm any resolution commitment.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "complaint",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["CONTEXTUAL LIABILITY"],
        "notes": (
            "2 flags from Layer 1 (confidence + complaint context) — still medium (2 < 3). "
            "LLM should catch 'full responsibility' + 'will ensure it does not happen again' "
            "as implicit liability and a forward guarantee."
        ),
    })

    cases.append({
        "case_id": "rk-004",
        "scenario": "Customer complaint dismissed with generic policy quote — specific grievance is not addressed",
        "boundary_type": "intent_mismatch",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_intent_urgency(complaint) -> 1 flag",
        "state": {
            "reply_text": (
                "Thank you for your feedback. Our return policy allows returns within 30 days "
                "for items in their original condition. Please refer to our terms and conditions "
                "for more details."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Standard policy information provided.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "complaint",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["INTENT MISMATCH"],
        "notes": (
            "LLM should detect that the reply ignores the specific complaint "
            "and deflects to generic policy — a dismissive response to a complaint "
            "is itself a risk (INTENT MISMATCH)."
        ),
    })

    cases.append({
        "case_id": "rk-005",
        "scenario": "Reply claims stock availability and implies a weekend delivery — both unverified",
        "boundary_type": "implied_commitment",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_unverified_claims (in stock, no retriever) -> 1 flag",
        "state": {
            "reply_text": (
                "Great news — the item is in stock and ready to dispatch. "
                "You should have it with you by the weekend."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Stock confirmed in reply but no retriever data to back this.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "product_inquiry",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["IMPLIED COMMITMENT"],
        "notes": (
            "'by the weekend' is an implicit delivery commitment not caught by the regex "
            "(needs ship/deliver/dispatch + by/before/within pattern). "
            "LLM should detect both the unverified stock and the implied delivery timeline."
        ),
    })

    cases.append({
        "case_id": "rk-006",
        "scenario": "Over-apologetic reply contains an implicit liability admission and a vague open-ended commitment",
        "boundary_type": "contextual_liability",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_tone(over-apologetic) + check_intent_urgency(complaint) -> 2 flags",
        "state": {
            "reply_text": (
                "I'm truly sorry for the distress this has caused you. We completely understand "
                "your frustration, and this should never have happened. We'll do everything "
                "in our power to make this right."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Complaint response drafted without sub-agent data.",
            "unverified_claims": [],
            "tone_flags": ["over-apologetic"],
            "intent_label": "complaint",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["CONTEXTUAL LIABILITY", "IMPLIED COMMITMENT"],
        "notes": (
            "'this should never have happened' = implicit liability admission; "
            "'everything in our power to make this right' = vague open commitment. "
            "LLM should upgrade to high."
        ),
    })

    cases.append({
        "case_id": "rk-007",
        "scenario": "Reply grants an extended return that the policy agent flagged as requiring owner approval",
        "boundary_type": "policy_approval_violated",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_policy_cross(requires_approval) -> 1 flag",
        "state": {
            "reply_text": (
                "Of course, I can arrange that extended return for you. "
                "Let's get this sorted right away."
            ),
            "sender_role": "customer",
            "completed_tasks": [
                _policy_task(
                    "p1",
                    "Check whether an extended return beyond 30 days is permitted for this customer",
                    "Extended returns beyond the 30-day policy window require owner approval. "
                    "Cannot be committed without review.",
                )
            ],
            "confidence_level": "high",
            "confidence_note": "Policy check returned requires_approval verdict.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "returns_query",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["IMPLIED COMMITMENT"],
        "notes": (
            "Layer 1 POLICY REQUIRES APPROVAL flag is correct. "
            "LLM should escalate because the reply ('Of course, I can arrange that') "
            "is granting the policy-blocked action rather than deferring it."
        ),
    })

    # ── GROUP 2: LLM should MAINTAIN medium (5 cases) ─────────────────────────

    cases.append({
        "case_id": "rk-008",
        "scenario": "Appropriately hedged reply with medium confidence — no concrete commitments made",
        "boundary_type": "maintain_hedged_reply",
        "expected_stable_level": "medium",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_confidence(medium) -> 1 flag",
        "state": {
            "reply_text": (
                "Based on the information currently available, your order should be processed "
                "within 3-5 business days. We'll confirm the exact timeline once everything "
                "is in our system."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "medium",
            "confidence_note": "Exact processing timeline not confirmed by retriever.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "order_query",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Hedged language ('should be processed', 'we'll confirm once'). "
            "The medium confidence flag is legitimate. "
            "LLM should find no new risks — maintain medium."
        ),
    })

    cases.append({
        "case_id": "rk-009",
        "scenario": "Neutral complaint acknowledgement — logs concern, no commitment or liability",
        "boundary_type": "maintain_complaint_response",
        "expected_stable_level": "medium",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_intent_urgency(complaint) -> 1 flag",
        "state": {
            "reply_text": (
                "Thank you for reaching out. We've logged your concern and our team will "
                "review it carefully. We'll be in touch if we need any further information."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Complaint acknowledgement — no specific data retrieved.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "complaint",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Complaint context flag is warranted (extra scrutiny). "
            "But reply is a neutral acknowledgement with no commitments or liability. "
            "LLM should maintain medium — the flag is correct, the reply is safe."
        ),
    })

    cases.append({
        "case_id": "rk-010",
        "scenario": "Stock mentioned with an explicit caveat to confirm before ordering",
        "boundary_type": "maintain_caveated_stock",
        "expected_stable_level": "medium",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_unverified_claims (in stock, no retriever) -> 1 flag",
        "state": {
            "reply_text": (
                "Our records show this item is in stock at our main warehouse. "
                "I'd recommend confirming current availability before placing a bulk order, "
                "as stock levels can change."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Stock level stated but not retrieved from live inventory.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "product_inquiry",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Flag is legitimate ('in stock' with no retriever). "
            "Reply immediately caveats with 'recommend confirming' and 'stock levels can change'. "
            "LLM should maintain medium — the flag is correct, the uncertainty is appropriately managed."
        ),
    })

    cases.append({
        "case_id": "rk-011",
        "scenario": "Reply defers a partner pricing request to management review — does not commit",
        "boundary_type": "maintain_policy_deferral",
        "expected_stable_level": "medium",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_policy_cross(requires_approval) -> 1 flag",
        "state": {
            "reply_text": (
                "A custom pricing arrangement of this kind would need to go through our "
                "management review process before we could commit to anything. "
                "I'll forward your request and you can expect to hear back within 1-2 business days."
            ),
            "sender_role": "partner",
            "completed_tasks": [
                _policy_task(
                    "p1",
                    "Check whether custom pricing arrangements for partners require approval",
                    "Custom pricing arrangements beyond standard partner terms require owner "
                    "approval before any commitment can be made.",
                )
            ],
            "confidence_level": "high",
            "confidence_note": "Policy check returned requires_approval for custom pricing.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "pricing_inquiry",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Reply correctly defers: 'would need to go through management review before "
            "we could commit to anything'. The policy approval flag is warranted for scrutiny "
            "but the reply handles it safely. LLM should maintain medium."
        ),
    })

    cases.append({
        "case_id": "rk-012",
        "scenario": "Stiff but accurate policy explanation to a partner — defensive tone, no dangerous content",
        "boundary_type": "maintain_defensive_tone",
        "expected_stable_level": "medium",
        "expected_requires_approval": True,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_tone(defensive) -> 1 flag",
        "state": {
            "reply_text": (
                "As stated in our terms and conditions, which are agreed to during account setup, "
                "all partnership arrangements fall under our standard 90-day review period. "
                "This is applied consistently for all partners."
            ),
            "sender_role": "partner",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Policy reference provided; factually grounded.",
            "unverified_claims": [],
            "tone_flags": ["defensive"],
            "intent_label": "partnership_query",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Stiff and policy-referencing, but factually accurate, no commitment, no liability. "
            "LLM should find no material new risks. Maintain medium."
        ),
    })

    # ── GROUP 3: LLM should DOWNGRADE to LOW (4 cases) ────────────────────────

    cases.append({
        "case_id": "rk-013",
        "scenario": "Pure acknowledgement reply with medium confidence — nothing claimable, nothing to verify",
        "boundary_type": "false_positive_confidence",
        "expected_stable_level": "low",
        "expected_requires_approval": False,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_confidence(medium) -> 1 flag (false positive for this reply)",
        "state": {
            "reply_text": (
                "Thank you for getting in touch. We'll look into this and get back to you "
                "with an update."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "medium",
            "confidence_note": "No specific data retrieved; acknowledgement only.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "general_inquiry",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Reply is a pure acknowledgement with zero factual claims. "
            "The medium confidence flag is a false positive — there is nothing to be wrong about. "
            "LLM should downgrade to low."
        ),
    })

    cases.append({
        "case_id": "rk-014",
        "scenario": "Empathetic apology with no liability admission or specific commitment",
        "boundary_type": "false_positive_tone",
        "expected_stable_level": "low",
        "expected_requires_approval": False,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_tone(over-apologetic) -> 1 flag (false positive for this reply)",
        "state": {
            "reply_text": (
                "I'm sorry you had to experience this inconvenience. "
                "We appreciate your patience and for bringing this to our attention."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Empathetic acknowledgement; no data required.",
            "unverified_claims": [],
            "tone_flags": ["over-apologetic"],
            "intent_label": "general_inquiry",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Reply expresses empathy but makes no specific commitments or fault admissions. "
            "'I'm sorry you experienced' != 'it was our fault'. Standard service language. "
            "LLM should downgrade to low."
        ),
    })

    cases.append({
        "case_id": "rk-015",
        "scenario": "Reply explicitly declines a policy-blocked request — does not commit to the approval-required action",
        "boundary_type": "false_positive_policy_approval",
        "expected_stable_level": "low",
        "expected_requires_approval": False,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_policy_cross(requires_approval) -> 1 flag (false positive for this reply)",
        "state": {
            "reply_text": (
                "Extended returns beyond our 30-day policy are outside what we can offer directly. "
                "Our management team reviews exceptions on a case-by-case basis, but I'm unable "
                "to commit to anything at this stage."
            ),
            "sender_role": "customer",
            "completed_tasks": [
                _policy_task(
                    "p1",
                    "Check whether an extended return beyond 30 days is permitted",
                    "Extended returns beyond 30 days require owner approval before any commitment.",
                )
            ],
            "confidence_level": "high",
            "confidence_note": "Policy verdict acknowledged; reply declines to commit.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "returns_query",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "Reply explicitly refuses to grant the blocked action and explicitly declines to commit. "
            "The approval flag is technically raised but the reply handles it correctly. "
            "LLM should downgrade to low."
        ),
    })

    cases.append({
        "case_id": "rk-016",
        "scenario": "Neutral complaint acknowledgement with no commitments — complaint intent flag is a false positive",
        "boundary_type": "false_positive_complaint",
        "expected_stable_level": "low",
        "expected_requires_approval": False,
        "is_boundary_case": False,
        "n_runs": 5,
        "layer1_trigger": "check_intent_urgency(complaint) -> 1 flag (false positive for this reply)",
        "state": {
            "reply_text": (
                "Thank you for your message. We take all feedback seriously and will pass "
                "your comments to the relevant team for review."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Standard feedback routing reply; no data needed.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "complaint",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "'Will pass your comments to the relevant team' is not a specific commitment. "
            "The complaint flag prompted scrutiny but the reply is demonstrably safe. "
            "LLM should downgrade to low."
        ),
    })

    # ── GROUP 4: BOUNDARY cases (2 cases) ─────────────────────────────────────

    cases.append({
        "case_id": "rk-017",
        "scenario": "BOUNDARY: Personal assurance to ensure the right outcome — soft guarantee, borderline high/medium",
        "boundary_type": "boundary_implied_commitment",
        "expected_stable_level": "high",
        "expected_requires_approval": True,
        "is_boundary_case": True,
        "n_runs": 5,
        "layer1_trigger": "check_confidence(medium) -> 1 flag",
        "state": {
            "reply_text": (
                "I'll look into this personally and make sure we find the right outcome for you."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "medium",
            "confidence_note": "No retriever data to confirm any resolution path.",
            "unverified_claims": [],
            "tone_flags": [],
            "intent_label": "general_inquiry",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": ["IMPLIED COMMITMENT"],
        "notes": (
            "BOUNDARY: 'Make sure we find the right outcome' carries a guarantee connotation. "
            "Expected stable level is high, but this is genuinely on the boundary. "
            "Flip rate here is diagnostic of how sensitively the LLM interprets soft guarantee language."
        ),
    })

    cases.append({
        "case_id": "rk-018",
        "scenario": "BOUNDARY: Vague offer of flexibility to a loyal customer — soft implied deal, borderline medium/high",
        "boundary_type": "boundary_vague_offer",
        "expected_stable_level": "medium",
        "expected_requires_approval": True,
        "is_boundary_case": True,
        "n_runs": 5,
        "layer1_trigger": "check_tone(defensive) -> 1 flag",
        "state": {
            "reply_text": (
                "While our standard pricing is firm, we always try to be flexible for our loyal "
                "customers. I'll see what options might be available on our end."
            ),
            "sender_role": "customer",
            "completed_tasks": [],
            "confidence_level": "high",
            "confidence_note": "Pricing reply without retriever guidance.",
            "unverified_claims": [],
            "tone_flags": ["defensive"],
            "intent_label": "pricing_inquiry",
            "urgency_level": "normal",
        },
        "expected_llm_flag_categories": [],
        "notes": (
            "BOUNDARY: 'I'll see what options might be available' is very vague — not a firm commitment. "
            "Sufficiently hedged language. Expected stable level is medium. "
            "Flip rate here is diagnostic of how the LLM treats vague commercial language."
        ),
    })

    return cases


# ── Validation and output ──────────────────────────────────────────────────────

def generate(force: bool = False) -> None:
    if OUTPUT_PATH.exists() and not force:
        print(
            f"Ground truth already exists at {OUTPUT_PATH}.\n"
            "Use --force to regenerate."
        )
        sys.exit(0)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cases = _build_cases()

    # Validate every case against Layer 1
    print(f"Validating {len(cases)} cases against Layer 1 deterministic rules...\n")
    all_ok = True
    layer1_summary: dict[str, int] = {}

    for entry in cases:
        level, flags = _compute_layer1(entry["state"])
        ok = level == "medium"
        tag = "OK" if ok else "FAIL"
        flag_summary = "; ".join(f[:60] for f in flags) if flags else "(none)"
        print(
            f"  [{tag}] {entry['case_id']}  layer1={level}  "
            f"flags={len(flags)}  ({entry['boundary_type']})"
        )
        if not ok:
            print(f"         flags: {flag_summary}")
            all_ok = False
        trigger = entry.get("layer1_trigger", "unknown")
        layer1_summary[trigger] = layer1_summary.get(trigger, 0) + 1

    print()
    if not all_ok:
        print(
            "[ERROR] One or more cases do not produce 'medium' from Layer 1. "
            "The LLM second pass will not fire for those cases. "
            "Fix the case definitions in _build_cases() before evaluating."
        )
        sys.exit(1)

    print(f"All {len(cases)} cases validated — Layer 1 produces 'medium' for every entry.")

    # Build boundary_type and expected_level distributions for metadata
    boundary_dist: dict[str, int] = {}
    level_dist: dict[str, int] = {}
    for c in cases:
        bt = c["boundary_type"]
        lvl = c["expected_stable_level"]
        boundary_dist[bt] = boundary_dist.get(bt, 0) + 1
        level_dist[lvl] = level_dist.get(lvl, 0) + 1

    dataset = {
        "metadata": {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(cases),
            "description": (
                "Each case produces 'medium' from the deterministic Layer 1 rules, "
                "ensuring the LLM second pass (risk_llm.py) always fires. "
                "n_runs repetitions measure consistency and correctness of the LLM layer."
            ),
            "boundary_type_distribution": boundary_dist,
            "expected_stable_level_distribution": level_dist,
            "layer1_trigger_distribution": layer1_summary,
            "notes": (
                "Cases are hard-coded in generate_ground_truth.py and validated "
                "against _compute_layer1() at generation time. No LLM is used for "
                "generation — linguistic variety is not the target; precise state "
                "control is."
            ),
        },
        "entries": cases,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"\nGround truth written -> {OUTPUT_PATH}  ({len(cases)} entries)")
    print("\nBoundary type distribution:")
    for bt, n in sorted(boundary_dist.items()):
        print(f"  {bt:<38} {n}")
    print("\nExpected stable level distribution:")
    for lvl, n in sorted(level_dist.items()):
        print(f"  {lvl:<10} {n}")
    print(
        "\nRun the evaluation:\n"
        "  uv run python tests/risk_node/evaluate.py"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate ground truth dataset for risk node LLM second pass evaluation."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing ground_truth_dataset.json if present.",
    )
    args = parser.parse_args()
    generate(force=args.force)
