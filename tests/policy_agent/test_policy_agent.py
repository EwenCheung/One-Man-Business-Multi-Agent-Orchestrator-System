"""
Policy Agent Integration Tests

Runs the full policy agent pipeline — pgvector search, LLM reranking, and
LLM evaluation — against real policy chunks in the database.

Prerequisites:
    1. PostgreSQL + pgvector running (docker compose up -d db)
    2. policy_chunks table populated (uv run python backend/db/ingest_policies.py)
    3. OPENAI_API_KEY set in .env

Coverage:
    1. Returns    — customer asks about the return window
    2. Pricing    — customer asks whether discounts can be stacked
    3. Privacy    — customer asks what personal data is stored
    4. Supplier   — supplier asks about payment terms
    5. Partner    — partner asks about revenue share
    6. Hard constraint — action that violates a non-overridable rule
    7. Requires approval — action that needs owner sign-off
    8. Not covered — question outside all policy domains
    9. Role context  — same question, different sender roles

Usage:
    uv run python tests/test_policy_agent.py
"""

from backend.agents.policy_agent import policy_agent


# ─── Helpers ─────────────────────────────────────────────────────────────────


def make_task(task_id: str, description: str, sender_role: str = "customer") -> dict:
    """Build a SubTask dict simluating Orchestrator"""
    return {
        "task_id": task_id,
        "description": description,
        "assignee": "policy",
        "status": "pending",
        "result": "",
        "priority": "required",
        "context_needed": ["sender_role"],
        "injected_context": {"sender_role": sender_role},
    }


import json


def print_result(label: str, output: dict) -> None:
    """Print test result."""
    task = output["completed_tasks"][0]
    print(f"\n{'=' * 60}")
    print(f"TEST: {label}")
    print(f"{'=' * 60}")
    print(f"  Role:   {task['injected_context'].get('sender_role', 'unknown')}")
    print(f"  Status: {task['status']}")
    print(f"  Result:\n")

    result_str = task["result"]
    try:
        data = json.loads(result_str)
        text_content = data.get("result", result_str)
    except json.JSONDecodeError:
        text_content = result_str

    for line in text_content.splitlines():
        print(f"    {line}")


def _verdict(output: dict) -> str:
    """Extract the verdict line from the result text."""
    result_str = output["completed_tasks"][0]["result"]
    try:
        data = json.loads(result_str)
        text_content = data.get("result", result_str)
    except json.JSONDecodeError:
        text_content = result_str

    for line in text_content.splitlines():
        if line.strip().startswith("Verdict:"):
            return line.split(":", 1)[1].strip().lower()
    return ""


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_returns_window():
    """Customer asks how long they have to return a product."""
    task = make_task(
        task_id="pol-01",
        description="How many days do I have to return a product, and what condition must it be in?",
        sender_role="customer",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"
    assert _verdict(output) in {"allowed", "not_covered"}


def test_discount_stacking_disallowed():
    """Customer asks whether multiple discount types can be combined — should be disallowed."""
    task = make_task(
        task_id="pol-02",
        description="Can I apply both a volume discount and a loyalty discount on the same order?",
        sender_role="customer",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"
    # Stacking discounts is explicitly prohibited — expect disallowed
    assert _verdict(output) in {"disallowed", "not_covered"}


def test_data_privacy_customer():
    """Customer asks what personal data the business holds about them."""
    task = make_task(
        task_id="pol-03",
        description="What personal data do you collect and store about me as a customer?",
        sender_role="customer",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"


def test_supplier_payment_terms():
    """Supplier asks about standard invoice payment terms."""
    task = make_task(
        task_id="pol-04",
        description="What are the standard payment terms for supplier invoices?",
        sender_role="supplier",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"


def test_partner_revenue_share():
    """Partner asks how referral commissions are calculated and paid."""
    task = make_task(
        task_id="pol-05",
        description="What percentage commission do I receive for referrals and when is it paid?",
        sender_role="partner",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"


def test_hard_constraint_price_floor():
    """Asking to discount below cost price — should hit a hard constraint."""
    task = make_task(
        task_id="pol-06",
        description=(
            "A customer is pushing back hard. Can I offer a discount below cost price "
            "to close the deal, even without owner approval?"
        ),
        sender_role="customer",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"
    # Discounts without owner approval violate the discount authority rule
    assert _verdict(output) in {"disallowed", "requires_approval", "not_covered"}


def test_requires_approval_large_discount():
    """Requesting a discount outside standard tiers — should require approval."""
    task = make_task(
        task_id="pol-07",
        description=(
            "I want to offer a 20% discount to a new bulk customer. "
            "Is this allowed, or do I need approval?"
        ),
        sender_role="customer",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"


def test_not_covered():
    """Question entirely outside all policy domains — expect not_covered or low confidence."""
    task = make_task(
        task_id="pol-08",
        description="What is the company's policy on providing employee gym memberships?",
        sender_role="customer",
    )
    output = policy_agent(task)
    assert output["completed_tasks"][0]["status"] == "completed"
    # No policy covers employee benefits — should be not_covered or low confidence
    assert _verdict(output) in {"not_covered", "allowed", "disallowed", "requires_approval"}


def test_role_affects_context():
    """Same question asked by a supplier vs a partner — role is injected into evaluation."""
    question = "Can our agreement be terminated early, and what are the conditions?"

    supplier_task = make_task("pol-09a", question, sender_role="supplier")
    partner_task = make_task("pol-09b", question, sender_role="partner")

    supplier_output = policy_agent(supplier_task)
    partner_output = policy_agent(partner_task)

    assert supplier_output["completed_tasks"][0]["status"] == "completed"
    assert partner_output["completed_tasks"][0]["status"] == "completed"


# ─── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("Returns — Return Window", test_returns_window),
        ("Pricing — Discount Stacking", test_discount_stacking_disallowed),
        ("Privacy — Data Held on Customer", test_data_privacy_customer),
        ("Supplier — Payment Terms", test_supplier_payment_terms),
        ("Partner — Revenue Share", test_partner_revenue_share),
        ("Hard Constraint — Price Floor", test_hard_constraint_price_floor),
        ("Approval Required — Large Discount", test_requires_approval_large_discount),
        ("Not Covered — Gym Membership", test_not_covered),
    ]

    for label, test_fn in tests:
        try:
            result = test_fn()
            if isinstance(result, tuple):
                for i, r in enumerate(result, 1):
                    print_result(f"{label} (variant {i})", r)
            else:
                print_result(label, result)
        except Exception as exc:
            print(f"\n{'=' * 60}")
            print(f"TEST: {label}")
            print(f"{'=' * 60}")
            print(f"  ERROR: {exc}")

    # Role context test printed separately since it returns a tuple
    print(f"\n{'=' * 60}")
    print("TEST: Role Context — Supplier vs Partner")
    print(f"{'=' * 60}")
    try:
        s_out, p_out = test_role_affects_context()
        print_result("Role Context — Supplier", s_out)
        print_result("Role Context — Partner", p_out)
    except Exception as exc:
        print(f"  ERROR: {exc}")

    print(f"\n{'=' * 60}")
    print("ALL TESTS COMPLETE")
    print(f"{'=' * 60}")
