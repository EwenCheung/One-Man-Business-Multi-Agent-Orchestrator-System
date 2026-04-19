import uuid

import pytest

from backend.config import settings
from backend.db.engine import SessionLocal
from backend.db.models import Product
from backend.tools.retrieval_tools import evaluate_discount_request


def _seeded_product_name(session):
    product = (
        session.query(Product)
        .filter(Product.owner_id == uuid.UUID(settings.OWNER_ID))
        .order_by(Product.name.asc())
        .first()
    )
    if not product:
        pytest.skip("Integration dataset has no seeded product for the configured owner.")
    return product.name


@pytest.mark.integration
def test_evaluate_discount_request_returns_internal_and_public_guidance():
    session = SessionLocal()
    try:
        product_name = _seeded_product_name(session)
        result = evaluate_discount_request(
            session,
            settings.OWNER_ID,
            product_name,
            20,
            10.0,
        )
        assert result["status"] == "ok"
        assert "cost_price" in result
        assert "max_discount_pct" in result
        assert "customer_safe_summary" in result
    finally:
        session.close()


@pytest.mark.integration
def test_large_discount_or_large_quantity_requires_approval():
    session = SessionLocal()
    try:
        product_name = _seeded_product_name(session)
        result = evaluate_discount_request(
            session,
            settings.OWNER_ID,
            product_name,
            120,
            20.0,
        )
        assert result["status"] == "ok"
        assert result["approval_required"] is True
    finally:
        session.close()
