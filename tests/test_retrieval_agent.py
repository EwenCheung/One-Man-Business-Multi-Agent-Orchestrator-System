"""
Retrieval Pipeline Integration Test

Simulates upstream SubTask prompts as if sent by the Orchestrator via Send(),
passes them through the retrieval_agent, and prints downstream results.

Covers all 4 roles + 1 access-denied scenario = 5 tests.
"""

import json

from backend.agents.retrieval_agent import retrieval_agent


def make_task(task_id: str, description: str, role: str, sender_id: str) -> dict:
    """Build a SubTask dict mimicking what the Orchestrator would produce."""
    return {
        "task_id": task_id,
        "description": description,
        "assignee": "retriever",
        "status": "pending",
        "result": "",
        "sender_role": role,
        "sender_id": sender_id,
    }


def print_result(label: str, output: dict):
    """Pretty-print a test result."""
    task = output["completed_tasks"][0]
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")
    print(f"  Role:        {task['sender_role']}")
    print(f"  Sender ID:   {task['sender_id']}")
    print(f"  Description: {task['description']}")
    print(f"  Status:      {task['status']}")
    print(f"  Result:")

    # Try to pretty-print JSON, fall back to raw string
    try:
        parsed = json.loads(task["result"])
        print(f"  {json.dumps(parsed, indent=4, default=str)}")
    except (json.JSONDecodeError, TypeError):
        print(f"  {task['result']}")


def test_customer_orders():
    """Customer (id=1) asks about their recent orders."""
    task = make_task(
        task_id="test-01",
        description="Show me my recent orders and their status.",
        role="customer",
        sender_id="1",
    )
    return retrieval_agent(task)


def test_supplier_contracts():
    """Supplier (id=1) asks about their active contracts."""
    task = make_task(
        task_id="test-02",
        description="What are my current supply contracts and product details?",
        role="supplier",
        sender_id="1",
    )
    return retrieval_agent(task)


def test_investor_roi():
    """Investor asks for product ROI analysis."""
    task = make_task(
        task_id="test-03",
        description="Give me the ROI breakdown for all products.",
        role="investor",
        sender_id="0",
    )
    return retrieval_agent(task)


def test_partner_products():
    """Partner (id=1) asks about their linked products."""
    task = make_task(
        task_id="test-04",
        description="Which products are linked to my partnership and what are the agreement details?",
        role="partner",
        sender_id="1",
    )
    return retrieval_agent(task)


def test_unknown_role_denied():
    """Unknown role should be denied access."""
    task = make_task(
        task_id="test-05",
        description="Show me everything in the database.",
        role="anonymous",
        sender_id="0",
    )
    return retrieval_agent(task)


if __name__ == "__main__":
    tests = [
        ("Customer — My Orders", test_customer_orders),
        ("Supplier — My Contracts", test_supplier_contracts),
        ("Investor — Product ROI", test_investor_roi),
        ("Partner — My Products", test_partner_products),
        ("Unknown Role — Access Denied", test_unknown_role_denied),
    ]

    for label, test_fn in tests:
        try:
            result = test_fn()
            print_result(label, result)
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"TEST: {label}")
            print(f"{'='*60}")
            print(f"  ERROR: {e}")

    print(f"\n{'='*60}")
    print("ALL 5 TESTS COMPLETE")
    print(f"{'='*60}")
