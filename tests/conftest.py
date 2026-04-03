import os

import pytest
from backend.db.engine import SessionLocal


@pytest.fixture(scope="session")
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_state():
    return {
        "messages": [],
        "sender_id": "test_sender",
        "sender_name": "Test User",
        "sender_role": "customer",
        "detected_intent": None,
        "is_safe": True,
        "risk_level": "low",
        "risk_flags": [],
        "business_context": [],
        "db_records": {},
        "tool_calls": [],
        "draft_response": "",
        "final_response": "",
        "requires_approval": False,
        "owner_id": "4c116430-f683-4a8a-91f7-546fa8bc5d76",
        "internal_monologue": [],
    }


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless INTEGRATION_TESTS=1 is set in the environment."""
    if os.environ.get("INTEGRATION_TESTS"):
        return
    skip_marker = pytest.mark.skip(
        reason="Integration test skipped by default. Set INTEGRATION_TESTS=1 to run."
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_marker)
