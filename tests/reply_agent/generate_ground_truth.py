"""
Ground Truth Generation for Reply Agent Evaluation

Strategy
--------
Each case supplies a complete PipelineState dict (raw_message, sender_role,
completed_tasks, soul_context, rules_context, etc.) and specifies the expected
structured-output fields that the reply agent should produce:

    expected_confidence_level      — "high" | "medium" | "low"
    expected_has_unverified_claims — True if unverified_claims should be non-empty
    expected_tone_flags            — exact set of tone anomaly labels expected

Unlike the risk node (which evaluates a separate LLM second pass over a fixed
reply_text), this benchmark evaluates the reply agent's SELF-ASSESSMENT of its
own generated output — three structured fields alongside the reply_text.

Cases are hard-coded in Python. Linguistic variety is not the goal; precise
control over what sub-agent data is (and is not) available is.

The 14 cases cover five scenario groups:

    GROUP 1 — Confidence level accuracy (5 cases)
        Tests that confidence_level correctly reflects completed_tasks coverage.

    GROUP 2 — Unverified claims accuracy (3 cases)
        Tests that unverified_claims presence/absence matches data gaps.

    GROUP 3 — Tone flag detection (3 cases)
        Tests no spurious flags in clean scenarios; one diagnostic speculative case.

    GROUP 4 — Role & policy compliance (2 cases)
        Owner internal data access; supplier firm response under policy constraint.

    BOUNDARY — Ambiguous confidence (1 case)
        Stale tracking data — model should rate medium, but low is defensible.

Pre-validation checks state consistency (not deterministic Layer 1, since the
reply agent has no equivalent pre-filter). Validation rules:
    - All required state fields must be present and non-empty.
    - expected_confidence_level="high" requires at least one completed_task.
    - expected_tone_flags values must be drawn from the four defined labels.

Output:
    tests/reply_agent/test_cases/ground_truth_dataset.json

Usage:
    uv run python tests/reply_agent/generate_ground_truth.py
    uv run python tests/reply_agent/generate_ground_truth.py --force
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "test_cases" / "ground_truth_dataset.json"

VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}
VALID_TONE_FLAGS = {"over-apologetic", "over-committed", "defensive", "speculative"}

# ── Shared stubs ───────────────────────────────────────────────────────────────

SOUL_STUB = (
    "You are a professional and helpful business representative for a UK-based "
    "e-commerce business. Your voice is warm, direct, and confident. You speak "
    "with authority grounded in facts and represent the business founder in all "
    "external communications. Never over-promise or speculate beyond confirmed "
    "information. If you cannot confirm something, commit to following up rather "
    "than guessing."
)

RULE_STUB = (
    "1. Never reveal internal cost prices, profit margins, or markup thresholds "
    "to customers, suppliers, or partners. The business owner has full access to "
    "all internal financial data.\n"
    "2. Discounts, extended returns, or special arrangements that go beyond "
    "standard published policy require owner approval. Do not commit to these "
    "without a verified approval verdict.\n"
    "3. When a policy agent returns a 'requires_approval' verdict, communicate "
    "that the request must be reviewed — do not grant it.\n"
    "4. Do not speculate about future projections, product launches, or business "
    "strategy without explicit owner instruction.\n"
    "5. Always close with a clear next step or call to action for the sender."
)


# ── Completed-task builders ────────────────────────────────────────────────────

def _retriever_task(task_id: str, description: str, result_text: str) -> dict:
    """Build a completed retriever sub-task with a readable result string."""
    return {
        "task_id": task_id,
        "assignee": "retriever",
        "description": description,
        "status": "completed",
        "result": result_text,
        "priority": "required",
        "context_needed": [],
        "injected_context": {},
    }


def _policy_task(task_id: str, description: str, result_text: str) -> dict:
    """Build a completed policy sub-task with a readable result string."""
    return {
        "task_id": task_id,
        "assignee": "policy",
        "description": description,
        "status": "completed",
        "result": result_text,
        "priority": "required",
        "context_needed": [],
        "injected_context": {},
    }


def _base_state(
    *,
    sender_role: str,
    sender_name: str,
    intent_label: str,
    urgency_level: str,
    raw_message: str,
    completed_tasks: list,
) -> dict:
    """Return a state dict with SOUL/RULE stubs and empty memory fields."""
    return {
        "sender_role": sender_role,
        "sender_name": sender_name,
        "intent_label": intent_label,
        "urgency_level": urgency_level,
        "raw_message": raw_message,
        "completed_tasks": completed_tasks,
        "soul_context": SOUL_STUB,
        "rules_context": RULE_STUB,
        "long_term_memory": "No long-term memory for this test case.",
        "sender_memory": "No sender-specific notes for this test case.",
        "short_term_memory": [],
    }


# ── Pre-validation ─────────────────────────────────────────────────────────────

def _validate_case(entry: dict) -> list[str]:
    """Return a list of validation errors. Empty list means the case is OK."""
    errors: list[str] = []
    state = entry.get("state", {})

    # Required state fields
    required_fields = [
        "sender_role", "sender_name", "intent_label", "urgency_level",
        "raw_message", "soul_context", "rules_context",
    ]
    for field in required_fields:
        if not state.get(field):
            errors.append(f"Missing or empty required state field: '{field}'")

    # Confidence level validity
    exp_conf = entry.get("expected_confidence_level")
    if exp_conf not in VALID_CONFIDENCE_LEVELS:
        errors.append(
            f"expected_confidence_level='{exp_conf}' is not one of {VALID_CONFIDENCE_LEVELS}"
        )

    # Logic: high confidence requires sub-agent backing
    tasks = state.get("completed_tasks", [])
    if exp_conf == "high" and not tasks:
        errors.append(
            "expected_confidence_level='high' but completed_tasks is empty. "
            "High confidence cannot be self-assessed without sub-agent data."
        )

    # Tone flag validity
    exp_tone = entry.get("expected_tone_flags", [])
    invalid_flags = set(exp_tone) - VALID_TONE_FLAGS
    if invalid_flags:
        errors.append(
            f"expected_tone_flags contains unrecognised labels: {invalid_flags}. "
            f"Valid labels: {VALID_TONE_FLAGS}"
        )

    # Keyword guards: must be lists
    for kw_field in ("keyword_must_include", "keyword_must_exclude"):
        kw = entry.get(kw_field, [])
        if not isinstance(kw, list):
            errors.append(f"'{kw_field}' must be a list, got {type(kw).__name__}")

    return errors


# ── Case definitions ───────────────────────────────────────────────────────────

def _build_cases() -> list[dict]:
    """Return all 14 ground-truth cases.

    Each entry has:
        case_id, scenario, boundary_type,
        expected_confidence_level, expected_has_unverified_claims,
        expected_tone_flags, is_boundary_case, n_runs,
        keyword_must_include, keyword_must_exclude,
        state, notes
    """
    cases: list[dict] = []

    # ── GROUP 1: Confidence level accuracy (5 cases) ──────────────────────────

    cases.append({
        "case_id": "ra-001",
        "scenario": "Both retriever and policy answered fully — dispatch confirmed, return policy confirmed",
        "boundary_type": "full_retriever_policy",
        "expected_confidence_level": "high",
        "expected_has_unverified_claims": False,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Alex",
            intent_label="order_query",
            urgency_level="normal",
            raw_message=(
                "Hi, I placed order #4521 last week. "
                "Can you confirm it has been dispatched and when it will arrive?"
            ),
            completed_tasks=[
                _retriever_task(
                    "r1",
                    "Retrieve dispatch status and delivery estimate for order #4521",
                    "Order #4521 has been dispatched on 2026-04-11. "
                    "Tracking reference: REF-8821. "
                    "Estimated delivery: 3–5 business days from dispatch "
                    "(expected between 2026-04-14 and 2026-04-16).",
                ),
                _policy_task(
                    "p1",
                    "Check return policy eligibility for recently dispatched orders",
                    "Standard 30-day return policy applies to all dispatched orders "
                    "received in original condition. No owner approval required to "
                    "communicate this policy to the customer.",
                ),
            ],
        ),
        "notes": (
            "Both questions answered by sub-agents. Dispatch date, tracking, and delivery "
            "window all confirmed. Return policy explicitly approved. Agent should self-assess "
            "as high confidence with no unverified claims."
        ),
    })

    cases.append({
        "case_id": "ra-002",
        "scenario": "Retriever confirmed stock but has no delivery estimate — delivery is unverified",
        "boundary_type": "partial_retriever_gap",
        "expected_confidence_level": "medium",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Sam",
            intent_label="product_inquiry",
            urgency_level="normal",
            raw_message=(
                "Is the Model Z headset still in stock? "
                "If I order today, when would it arrive?"
            ),
            completed_tasks=[
                _retriever_task(
                    "r1",
                    "Check stock availability and delivery estimate for Model Z headset",
                    "Model Z headset: IN STOCK. Available quantity: 8 units at main warehouse. "
                    "Delivery estimates are not available from the current dataset — "
                    "standard carrier timelines apply but no confirmed ETA can be provided.",
                ),
            ],
        ),
        "notes": (
            "Stock confirmed, but retriever explicitly states delivery estimate is unavailable. "
            "Agent must hedge on delivery → medium confidence, delivery timeline in unverified_claims."
        ),
    })

    cases.append({
        "case_id": "ra-003",
        "scenario": "No sub-agent data — specific pricing question with nothing confirmed",
        "boundary_type": "no_sub_agent_data",
        "expected_confidence_level": "low",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Jordan",
            intent_label="pricing_inquiry",
            urgency_level="normal",
            raw_message=(
                "Can you give me a breakdown of pricing for 200 units of the "
                "Pro Series kit, including any volume discounts?"
            ),
            completed_tasks=[],
        ),
        "notes": (
            "No sub-agent tasks completed. Agent has zero verified data on pricing or "
            "volume discounts. Must hedge everything and commit to follow-up → low confidence, "
            "multiple unverified claims."
        ),
    })

    cases.append({
        "case_id": "ra-004",
        "scenario": "Policy explicitly approved the requested return — agent can confirm directly",
        "boundary_type": "policy_approved_direct",
        "expected_confidence_level": "high",
        "expected_has_unverified_claims": False,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Morgan",
            intent_label="returns_query",
            urgency_level="normal",
            raw_message=(
                "I purchased this 12 days ago and it arrived completely unopened. "
                "Can I return it?"
            ),
            completed_tasks=[
                _policy_task(
                    "p1",
                    "Check return eligibility for 12-day-old purchase in original unopened condition",
                    "APPROVED: Returns within 30 days in original, unopened condition are accepted. "
                    "No owner approval required. Standard returns process applies — "
                    "customer should use the returns portal or contact support to arrange collection.",
                ),
            ],
        ),
        "notes": (
            "Policy explicitly approved the return with no caveats. Agent can confirm the "
            "return directly → high confidence, empty unverified_claims."
        ),
    })

    cases.append({
        "case_id": "ra-005",
        "scenario": "Policy requires owner approval for late return — agent must defer, cannot confirm outcome",
        "boundary_type": "policy_requires_approval",
        "expected_confidence_level": "medium",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Casey",
            intent_label="returns_query",
            urgency_level="normal",
            raw_message=(
                "I bought this 45 days ago and never got around to trying it. "
                "Is there any flexibility on the return window?"
            ),
            completed_tasks=[
                _policy_task(
                    "p1",
                    "Check return eligibility for 45-day-old purchase beyond standard policy window",
                    "REQUIRES OWNER APPROVAL: Returns beyond 30 days fall outside the standard "
                    "policy window. Exceptions may be considered on a case-by-case basis but require "
                    "owner review before any commitment can be made. "
                    "Do not promise an exception to the customer.",
                ),
            ],
        ),
        "notes": (
            "Policy verdict is requires_approval — agent cannot confirm whether the exception "
            "will be granted. Must defer to review. Medium confidence (policy context is known, "
            "outcome is not). Unverified: whether exception will be approved."
        ),
    })

    # ── GROUP 2: Unverified claims accuracy (3 cases) ─────────────────────────

    cases.append({
        "case_id": "ra-006",
        "scenario": "Retriever returned complete, specific order status — all claims backed",
        "boundary_type": "all_claims_backed",
        "expected_confidence_level": "high",
        "expected_has_unverified_claims": False,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Riley",
            intent_label="order_query",
            urgency_level="normal",
            raw_message="What is the status of my order?",
            completed_tasks=[
                _retriever_task(
                    "r1",
                    "Retrieve current order status for customer Riley",
                    "Order #7721: Dispatched 2026-04-12. Tracking reference: ABC-123 (DPD). "
                    "Current status: In transit. Estimated delivery: Monday 2026-04-14.",
                ),
            ],
        ),
        "notes": (
            "Retriever returned specific, complete data: order number, dispatch date, "
            "tracking reference, carrier, and delivery date. Agent should use all of it "
            "and self-assess as high confidence with empty unverified_claims."
        ),
    })

    cases.append({
        "case_id": "ra-007",
        "scenario": "Order confirmed but no dispatch date yet — delivery timeline cannot be stated",
        "boundary_type": "delivery_not_retrieved",
        "expected_confidence_level": "medium",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Drew",
            intent_label="order_query",
            urgency_level="normal",
            raw_message=(
                "I ordered 3 days ago and haven't heard anything about shipping. "
                "When will it arrive?"
            ),
            completed_tasks=[
                _retriever_task(
                    "r1",
                    "Retrieve order status and dispatch information for recent order",
                    "Order confirmed and currently in processing queue. "
                    "Expected dispatch within 1–2 business days. "
                    "No dispatch confirmation or tracking number available yet. "
                    "Delivery date cannot be confirmed until dispatch occurs.",
                ),
            ],
        ),
        "notes": (
            "Order exists but no dispatch or delivery data. Retriever explicitly states "
            "'delivery date cannot be confirmed'. Agent must hedge → medium confidence, "
            "delivery timeline in unverified_claims."
        ),
    })

    cases.append({
        "case_id": "ra-008",
        "scenario": "No price data retrieved, bulk discount requires approval — nothing confirmed on pricing",
        "boundary_type": "price_not_retrieved",
        "expected_confidence_level": "low",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Blake",
            intent_label="pricing_inquiry",
            urgency_level="normal",
            raw_message=(
                "What is your unit price for 100 units? Can you offer a bulk discount?"
            ),
            completed_tasks=[
                _policy_task(
                    "p1",
                    "Check whether bulk discounts are available for orders of 100 units",
                    "REQUIRES OWNER APPROVAL: Bulk order discounts for quantities above 50 units "
                    "must be reviewed and approved by the owner before any pricing commitment. "
                    "Standard list pricing applies until an approved quote is issued. "
                    "No unit pricing data is available from the policy agent — "
                    "pricing must be retrieved separately.",
                ),
            ],
        ),
        "notes": (
            "Policy confirms bulk discount needs approval but provides no price data. "
            "No retriever task ran to fetch unit pricing. Agent cannot quote any price "
            "or commit to a discount → low confidence, price and discount in unverified_claims."
        ),
    })

    # ── GROUP 3: Tone flag detection (3 cases) ────────────────────────────────

    cases.append({
        "case_id": "ra-009",
        "scenario": "Standard factual partner query — payment terms confirmed, clean reply expected",
        "boundary_type": "clean_factual_reply",
        "expected_confidence_level": "high",
        "expected_has_unverified_claims": False,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="partner",
            sender_name="Fintech Partners Ltd",
            intent_label="payment_terms_inquiry",
            urgency_level="normal",
            raw_message=(
                "Could you confirm your standard payment terms for partner accounts?"
            ),
            completed_tasks=[
                _policy_task(
                    "p1",
                    "Retrieve standard payment terms for partner accounts",
                    "Standard partner payment terms: Net 30 days from invoice date. "
                    "Early payment discount: 2% if settled within 10 days (2/10 net 30). "
                    "Late payment charge: 1.5% per month on overdue balances. "
                    "These terms apply to all active partner accounts unless separately negotiated. "
                    "No owner approval required to communicate these terms.",
                ),
            ],
        ),
        "notes": (
            "Policy confirmed full payment terms with no ambiguity. Agent should produce a "
            "clean, factual reply with no tone anomalies. Tests that the agent does not "
            "generate false-positive tone flags on a straightforward factual response."
        ),
    })

    cases.append({
        "case_id": "ra-010",
        "scenario": "Damaged item complaint with no sub-agent data — agent must acknowledge and follow up",
        "boundary_type": "complaint_handled_neutrally",
        "expected_confidence_level": "low",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Jamie",
            intent_label="complaint",
            urgency_level="high",
            raw_message=(
                "My order arrived today and several items are damaged. "
                "This is completely unacceptable and I want this resolved immediately."
            ),
            completed_tasks=[],
        ),
        "notes": (
            "No order data available. Agent must acknowledge the complaint and commit to "
            "follow-up without admitting liability or making open-ended commitments. "
            "SOUL/RULE guide toward a professional empathetic response, not over-apologetic "
            "or over-committed. Expected: low confidence (no data), unverified (damage "
            "details unknown), and crucially NO tone flags — clean handling."
        ),
    })

    cases.append({
        "case_id": "ra-011",
        "scenario": "BOUNDARY/DIAGNOSTIC: Investor asks for growth projections — only current data available",
        "boundary_type": "boundary_speculative_investor",
        "expected_confidence_level": "medium",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": ["speculative"],
        "is_boundary_case": True,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="investor",
            sender_name="Venture Capital Group",
            intent_label="investor_inquiry",
            urgency_level="normal",
            raw_message=(
                "We are considering a potential investment. Could you walk us through "
                "your projected growth for the next 12 months?"
            ),
            completed_tasks=[
                _retriever_task(
                    "r1",
                    "Retrieve current business performance metrics for investor review",
                    "Current year revenue to date (April 2026): £312,000. "
                    "Year-on-year growth rate vs same period last year: +18%. "
                    "Note: forward-looking projections and financial forecasts are not "
                    "available in the current dataset.",
                ),
            ],
        ),
        "notes": (
            "BOUNDARY/DIAGNOSTIC: Current metrics confirmed but no forecast data exists. "
            "RULE prohibits speculating about financial projections without owner instruction. "
            "Agent must either stay grounded in current data (no speculative flag) or "
            "make forward-looking claims (speculative flag expected). "
            "Flip rate here is diagnostic of how the model balances investor tone posture "
            "against the speculative constraint."
        ),
    })

    # ── GROUP 4: Role & policy compliance (2 cases) ───────────────────────────

    cases.append({
        "case_id": "ra-012",
        "scenario": "Owner requests sales summary with margins — full internal data should be disclosed",
        "boundary_type": "owner_internal_access",
        "expected_confidence_level": "high",
        "expected_has_unverified_claims": False,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": ["55", "50", "70"],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="owner",
            sender_name="Owner",
            intent_label="business_metrics",
            urgency_level="normal",
            raw_message=(
                "Give me this month's sales summary including the margin on our top 3 products."
            ),
            completed_tasks=[
                _retriever_task(
                    "r1",
                    "Retrieve April 2026 sales performance and gross margin by product",
                    "April 2026 Sales Summary:\n"
                    "  Total revenue: £28,400\n"
                    "  Top 3 products by revenue:\n"
                    "    1. Pro Series Kit  — revenue £9,200, cost £4,100, gross margin 55.4%\n"
                    "    2. Model Z Headset — revenue £7,800, cost £3,900, gross margin 50.0%\n"
                    "    3. Cable Bundle    — revenue £5,400, cost £1,620, gross margin 70.0%\n"
                    "  Blended gross margin (month): 57.1%",
                ),
            ],
        ),
        "notes": (
            "Owner role — RULE grants full access to internal cost and margin data. "
            "Retriever returned complete margin figures. Agent should disclose all figures "
            "including cost prices and margins without redaction. "
            "keyword_must_include checks that margin percentages (55, 50, 70) appear in reply_text. "
            "High confidence, empty unverified_claims."
        ),
    })

    cases.append({
        "case_id": "ra-013",
        "scenario": "Supplier proposes 15% price increase — policy caps approved increases at 5%",
        "boundary_type": "supplier_firm_no_apology",
        "expected_confidence_level": "medium",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": False,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="supplier",
            sender_name="UK Component Supplies Ltd",
            intent_label="negotiation",
            urgency_level="normal",
            raw_message=(
                "We need to discuss our upcoming contract renewal. "
                "We are proposing a 15% price increase across all product lines "
                "due to rising material costs."
            ),
            completed_tasks=[
                _policy_task(
                    "p1",
                    "Check approved supplier price increase limits for contract renewal",
                    "Supplier contract terms: annual price increases up to 5% are pre-approved "
                    "and can be accepted without owner review. "
                    "Increases between 5–15% require owner approval before any commitment. "
                    "Increases above 15% cannot be agreed at agent level under any circumstances. "
                    "Current contract valid until 2026-06-30.",
                ),
            ],
        ),
        "notes": (
            "Policy caps pre-approved increases at 5%. The 15% proposal exceeds the cap and "
            "requires owner approval. Agent should communicate the policy position firmly and "
            "without apology (supplier tone: firm, confident), and defer the 15% to review. "
            "Medium confidence (can confirm the 5% cap, cannot confirm the outcome of review). "
            "Unverified: whether owner will approve an increase above 5%. "
            "Expected: no tone flags — particularly no 'over-apologetic' (supplier must be firm)."
        ),
    })

    # ── BOUNDARY: Stale tracking data (1 case) ────────────────────────────────

    cases.append({
        "case_id": "ra-014",
        "scenario": "BOUNDARY: Order dispatched but tracking data is 5 days stale — status unknown",
        "boundary_type": "boundary_stale_tracking",
        "expected_confidence_level": "medium",
        "expected_has_unverified_claims": True,
        "expected_tone_flags": [],
        "is_boundary_case": True,
        "n_runs": 7,
        "keyword_must_include": [],
        "keyword_must_exclude": [],
        "state": _base_state(
            sender_role="customer",
            sender_name="Taylor",
            intent_label="order_query",
            urgency_level="high",
            raw_message=(
                "My order was supposed to arrive last Monday and it's now Thursday. "
                "It still hasn't turned up. Where is it?"
            ),
            completed_tasks=[
                _retriever_task(
                    "r1",
                    "Retrieve order tracking and current delivery status for overdue order",
                    "Order #5503: Dispatched 2026-04-08. Estimated delivery window: 3–5 business days. "
                    "Last tracking scan: 2026-04-09 (5 days ago, no further scan updates recorded). "
                    "Current delivery status: UNKNOWN — tracking data is stale. "
                    "The order may be delayed or in transit without scan events. "
                    "A carrier investigation may be required.",
                ),
            ],
        ),
        "notes": (
            "BOUNDARY: Order was dispatched but tracking has been stale for 5 days — "
            "the order is overdue and its current location is unknown. "
            "Agent has some data (dispatch confirmed) but no current status → medium confidence "
            "is the most defensible call, with current status in unverified_claims. "
            "Flip rate here is diagnostic: model may rate as 'low' given the unknown status."
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

    print(f"Validating {len(cases)} cases...\n")
    all_ok = True

    for entry in cases:
        errors = _validate_case(entry)
        tag = "OK" if not errors else "FAIL"
        conf = entry.get("expected_confidence_level", "?")
        tasks_n = len(entry.get("state", {}).get("completed_tasks", []))
        print(
            f"  [{tag}] {entry['case_id']}  {entry['boundary_type']}"
            f"  expected_confidence={conf}  tasks={tasks_n}"
        )
        for err in errors:
            print(f"         ERROR: {err}")
            all_ok = False

    print()
    if not all_ok:
        print(
            "[ERROR] One or more cases failed validation. "
            "Fix the case definitions in _build_cases() before evaluating."
        )
        sys.exit(1)

    print(f"All {len(cases)} cases validated.")

    # Build distribution metadata
    conf_dist: dict[str, int] = {}
    boundary_dist: dict[str, int] = {}
    for c in cases:
        lvl = c["expected_confidence_level"]
        bt = c["boundary_type"]
        conf_dist[lvl] = conf_dist.get(lvl, 0) + 1
        boundary_dist[bt] = boundary_dist.get(bt, 0) + 1

    dataset = {
        "metadata": {
            "version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(cases),
            "description": (
                "Each case provides a complete PipelineState and specifies the expected "
                "structured-output fields (confidence_level, has_unverified_claims, tone_flags) "
                "for the reply agent. n_runs repetitions measure consistency and accuracy "
                "of the agent's self-assessment."
            ),
            "boundary_type_distribution": boundary_dist,
            "expected_confidence_distribution": conf_dist,
            "notes": (
                "Cases are hard-coded in generate_ground_truth.py and pre-validated for "
                "state consistency. No LLM is used for generation. "
                "n_runs=7 (vs 5 for risk node) because the reply agent runs at temperature=0.3."
            ),
        },
        "entries": cases,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"\nGround truth written -> {OUTPUT_PATH}  ({len(cases)} entries)")
    print("\nExpected confidence distribution:")
    for lvl, n in sorted(conf_dist.items()):
        print(f"  {lvl:<10} {n}")
    print("\nBoundary type distribution:")
    for bt, n in sorted(boundary_dist.items()):
        print(f"  {bt:<40} {n}")
    print(
        "\nRun the evaluation:\n"
        "  uv run python tests/reply_agent/evaluate.py"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate ground truth dataset for reply agent structured-output evaluation."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing ground_truth_dataset.json if present.",
    )
    args = parser.parse_args()
    generate(force=args.force)
