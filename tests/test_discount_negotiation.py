from backend.db.engine import SessionLocal
from backend.tools.retrieval_tools import evaluate_discount_request


def test_evaluate_discount_request_returns_internal_and_public_guidance():
    session = SessionLocal()
    try:
        result = evaluate_discount_request(session, "Wireless Mouse", 20, 10.0)
        assert result["status"] == "ok"
        assert "cost_price" in result
        assert "max_discount_pct" in result
        assert "customer_safe_summary" in result
    finally:
        session.close()


def test_large_discount_or_large_quantity_requires_approval():
    session = SessionLocal()
    try:
        result = evaluate_discount_request(session, "Wireless Mouse", 120, 20.0)
        assert result["status"] == "ok"
        assert result["approval_required"] is True
    finally:
        session.close()
