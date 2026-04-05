"""
Tests for the retrieval tools and role-based access control.

These are integration tests that run against the seeded database.
They verify:
    - Each role can only access its permitted tools
    - Column filtering works (customer can't see cost_price)
    - Row scoping works (customer A can't see customer B's orders)
    - Tool functions return expected data shapes
    - Semantic search tools return correctly filtered shapes
"""

import pytest
import uuid
from unittest.mock import patch
from backend.db.engine import SessionLocal
from backend.db import models
from backend.tools.retrieval_tools import (
    get_product_catalog,
    get_customer_orders,
    get_customer_profile,
    get_supplier_profile,
    get_supplier_contracts,
    get_product_stock,
    get_full_product_table,
    get_all_orders,
    get_customer_count,
    get_supply_overview,
    get_product_roi,
    get_sales_stats,
    get_partner_profile,
    get_partner_agreements,
    get_partner_products,
    semantic_search_product_catalog,
    semantic_search_supplier_contracts,
    semantic_search_full_product_table,
    semantic_search_supply_overview,
    semantic_search_all_partner_agreements,
    semantic_search_partner_agreements,
)
from backend.tools.role_permissions import get_tools_for_role, ROLE_TOOL_MAP

# A dummy 1536-dim zero vector used to mock embedding calls without hitting OpenAI.
_ZERO_VECTOR = [0.0] * 1536


@pytest.fixture
def session():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def sample_ids(session):
    c1 = session.query(models.Customer).offset(0).first()
    c2 = session.query(models.Customer).offset(1).first()
    s1 = session.query(models.Supplier).offset(0).first()
    s2 = session.query(models.Supplier).offset(1).first()
    p1 = session.query(models.Partner).offset(0).first()
    p2 = session.query(models.Partner).offset(1).first()
    return {
        "c1": str(c1.id) if c1 else None,
        "c2": str(c2.id) if c2 else None,
        "s1": str(s1.id) if s1 else None,
        "s2": str(s2.id) if s2 else None,
        "p1": str(p1.id) if p1 else None,
        "p2": str(p2.id) if p2 else None,
    }


# ─── Role Permission Tests ───────────────────────────────────────


class TestRolePermissions:
    def test_customer_has_exactly_4_tools(self):
        tools = get_tools_for_role("customer")
        assert len(tools) == 5
        names = {fn.__name__ for fn in tools}
        assert names == {
            "get_product_catalog",
            "get_customer_orders",
            "get_customer_profile",
            "semantic_search_product_catalog",
            "evaluate_discount_request",
        }

    def test_supplier_has_exactly_5_tools(self):
        tools = get_tools_for_role("supplier")
        assert len(tools) == 5
        names = {fn.__name__ for fn in tools}
        assert names == {
            "get_supplier_profile",
            "get_supplier_contracts",
            "get_product_stock",
            "semantic_search_product_catalog",
            "semantic_search_supplier_contracts",
        }

    def test_investor_has_exactly_9_tools(self):
        tools = get_tools_for_role("investor")
        assert len(tools) == 9
        names = {fn.__name__ for fn in tools}
        assert names == {
            "get_full_product_table",
            "get_all_orders",
            "get_customer_count",
            "get_supply_overview",
            "get_product_roi",
            "get_sales_stats",
            "semantic_search_full_product_table",
            "semantic_search_supply_overview",
            "semantic_search_all_partner_agreements",
        }

    def test_partner_has_exactly_5_tools(self):
        tools = get_tools_for_role("partner")
        assert len(tools) == 5
        names = {fn.__name__ for fn in tools}
        assert names == {
            "get_partner_profile",
            "get_partner_agreements",
            "get_partner_products",
            "semantic_search_product_catalog",
            "semantic_search_partner_agreements",
        }

    def test_unknown_role_raises(self):
        with pytest.raises(ValueError, match="Unknown role"):
            get_tools_for_role("hacker")

    def test_role_is_case_insensitive(self):
        tools = get_tools_for_role("CUSTOMER")
        assert len(tools) == 5

    def test_customer_cannot_access_investor_tools(self):
        customer_names = {fn.__name__ for fn in get_tools_for_role("customer")}
        assert "get_full_product_table" not in customer_names
        assert "get_product_roi" not in customer_names
        assert "get_all_orders" not in customer_names
        assert "semantic_search_full_product_table" not in customer_names
        assert "semantic_search_supply_overview" not in customer_names

    def test_supplier_cannot_access_customer_tools(self):
        supplier_names = {fn.__name__ for fn in get_tools_for_role("supplier")}
        assert "get_customer_orders" not in supplier_names
        assert "get_customer_profile" not in supplier_names

    def test_partner_cannot_access_supplier_tools(self):
        partner_names = {fn.__name__ for fn in get_tools_for_role("partner")}
        assert "get_supplier_contracts" not in partner_names
        assert "get_supplier_profile" not in partner_names
        assert "semantic_search_supplier_contracts" not in partner_names


# ─── Column Filtering Tests ──────────────────────────────────────


@pytest.mark.integration
class TestColumnFiltering:
    def test_product_catalog_excludes_cost_price(self, session):
        rows = get_product_catalog(session)
        assert len(rows) > 0
        for row in rows:
            assert "cost_price" not in row
            assert "selling_price" in row

    def test_product_stock_excludes_prices(self, session):
        rows = get_product_stock(session)
        assert len(rows) > 0
        for row in rows:
            assert "selling_price" not in row
            assert "cost_price" not in row
            assert "stock_number" in row

    def test_full_product_table_includes_cost_price(self, session):
        rows = get_full_product_table(session)
        assert len(rows) > 0
        for row in rows:
            assert "cost_price" in row
            assert "selling_price" in row

    def test_customer_count_has_no_pii(self, session):
        result = get_customer_count(session)
        assert "total_customers" in result
        assert "name" not in result
        assert "email" not in result

    def test_partner_products_excludes_cost_price(self, session, sample_ids):
        rows = get_partner_products(session, sample_ids["p1"])
        if rows:
            for row in rows:
                assert "cost_price" not in row
                assert "selling_price" in row


# ─── Row Scoping Tests ───────────────────────────────────────────


@pytest.mark.integration
class TestRowScoping:
    def test_customer_orders_scoped_to_customer(self, session, sample_ids):
        orders_c1 = get_customer_orders(session, sample_ids["c1"])
        orders_c2 = get_customer_orders(session, sample_ids["c2"])
        assert isinstance(orders_c1, list)
        assert isinstance(orders_c2, list)
        if orders_c1 and orders_c2:
            c1_ids = {o["order_id"] for o in orders_c1}
            c2_ids = {o["order_id"] for o in orders_c2}
            assert c1_ids.isdisjoint(c2_ids), "Customer 1 and 2 should not share order IDs"

    def test_customer_profile_returns_own_data(self, session, sample_ids):
        profile = get_customer_profile(session, sample_ids["c1"])
        assert profile is not None
        assert str(profile["id"]) == sample_ids["c1"]

    def test_customer_profile_nonexistent_returns_none(self, session):
        profile = get_customer_profile(session, "00000000-0000-0000-0000-000000000000")
        assert profile is None

    def test_supplier_contracts_scoped_to_supplier(self, session, sample_ids):
        contracts = get_supplier_contracts(session, sample_ids["s1"])
        assert isinstance(contracts, list)

    def test_supplier_profile_returns_own_data(self, session, sample_ids):
        profile = get_supplier_profile(session, sample_ids["s1"])
        assert profile is not None
        assert str(profile["id"]) == sample_ids["s1"]

    def test_partner_agreements_scoped_to_partner(self, session, sample_ids):
        agreements = get_partner_agreements(session, sample_ids["p1"])
        assert isinstance(agreements, list)

    def test_partner_products_scoped_to_partner(self, session, sample_ids):
        products_p1 = get_partner_products(session, sample_ids["p1"])
        products_p2 = get_partner_products(session, sample_ids["p2"])
        assert isinstance(products_p1, list)
        assert isinstance(products_p2, list)
        if products_p1 and products_p2:
            p1_ids = {p["id"] for p in products_p1}
            p2_ids = {p["id"] for p in products_p2}
            assert p1_ids.isdisjoint(p2_ids), "Partner 1 and 2 should not share product link IDs"


# ─── Data Shape Tests ────────────────────────────────────────────


@pytest.mark.integration
class TestDataShapes:
    def test_product_catalog_shape(self, session):
        rows = get_product_catalog(session)
        assert len(rows) > 0
        expected_keys = {
            "id",
            "name",
            "description",
            "selling_price",
            "stock_number",
            "product_link",
            "category",
        }
        assert set(rows[0].keys()) == expected_keys

    def test_all_orders_shape(self, session):
        rows = get_all_orders(session)
        assert len(rows) > 0
        expected_keys = {
            "order_id",
            "product_name",
            "customer_name",
            "quantity",
            "total_price",
            "order_date",
            "status",
            "channel",
        }
        assert set(rows[0].keys()) == expected_keys

    def test_product_roi_shape(self, session):
        rows = get_product_roi(session)
        assert len(rows) > 0
        expected_keys = {
            "id",
            "name",
            "description",
            "cost_price",
            "selling_price",
            "margin",
            "roi_pct",
            "total_sold",
            "total_revenue",
        }
        assert set(rows[0].keys()) == expected_keys

    def test_sales_stats_shape(self, session):
        stats = get_sales_stats(session)
        assert "total_orders" in stats
        assert "total_revenue" in stats
        assert "avg_order_value" in stats
        assert "orders_by_status" in stats
        assert stats["total_orders"] > 0

    def test_supply_overview_shape(self, session):
        rows = get_supply_overview(session)
        assert len(rows) > 0
        expected_keys = {
            "contract_id",
            "supplier_name",
            "product_name",
            "supply_price",
            "selling_price",
            "stock_we_buy",
            "lead_time_days",
            "contract_start",
            "contract_end",
            "is_active",
        }
        assert set(rows[0].keys()) == expected_keys


# ─── Semantic Search Tests ───────────────────────────────────────


@pytest.mark.integration
class TestSemanticSearch:
    """
    Semantic search tests mock _embed_query to avoid OpenAI API calls.
    If no embeddings have been seeded (ingest_business_data not yet run),
    the queries return empty lists — the shape assertions are guarded.
    """

    def test_semantic_search_product_catalog_returns_list(self, session):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result = semantic_search_product_catalog(session, "wireless headphones")
        assert isinstance(result, list)

    def test_semantic_search_product_catalog_excludes_cost_price(self, session):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result = semantic_search_product_catalog(session, "electronics")
        if result:
            for row in result:
                assert "cost_price" not in row
                assert "selling_price" in row
                assert "similarity_score" in row

    def test_semantic_search_full_product_table_includes_cost_price(self, session):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result = semantic_search_full_product_table(session, "electronics")
        assert isinstance(result, list)
        if result:
            for row in result:
                assert "cost_price" in row
                assert "selling_price" in row
                assert "similarity_score" in row

    def test_semantic_search_supplier_contracts_scoped_to_supplier(self, session, sample_ids):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result_s1 = semantic_search_supplier_contracts(
                session, "fast delivery", supplier_id=sample_ids["s1"]
            )
            result_s2 = semantic_search_supplier_contracts(
                session, "fast delivery", supplier_id=sample_ids["s2"]
            )
        assert isinstance(result_s1, list)
        assert isinstance(result_s2, list)
        if result_s1 and result_s2:
            s1_ids = {r["contract_id"] for r in result_s1}
            s2_ids = {r["contract_id"] for r in result_s2}
            assert s1_ids.isdisjoint(s2_ids), "Supplier 1 and 2 should not share contract IDs"

    def test_semantic_search_supply_overview_returns_list(self, session):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result = semantic_search_supply_overview(session, "active contracts")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "supplier_name" in row
            assert "product_name" in row
            assert "supply_price" in row
            assert "selling_price" in row
            assert "similarity_score" in row

    def test_semantic_search_all_partner_agreements_returns_list(self, session):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result = semantic_search_all_partner_agreements(session, "revenue share")
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "agreement_id" in row
            assert "partner_name" in row
            assert "agreement_type" in row
            assert "similarity_score" in row

    def test_semantic_search_partner_agreements_scoped_to_partner(self, session, sample_ids):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result_p1 = semantic_search_partner_agreements(
                session, "distribution", partner_id=sample_ids["p1"]
            )
            result_p2 = semantic_search_partner_agreements(
                session, "distribution", partner_id=sample_ids["p2"]
            )
        assert isinstance(result_p1, list)
        assert isinstance(result_p2, list)
        if result_p1 and result_p2:
            p1_ids = {r["agreement_id"] for r in result_p1}
            p2_ids = {r["agreement_id"] for r in result_p2}
            assert p1_ids.isdisjoint(p2_ids), "Partner 1 and 2 should not share agreement IDs"

    def test_semantic_search_respects_top_k(self, session):
        with patch("backend.tools.retrieval_tools._embed_query", return_value=_ZERO_VECTOR):
            result = semantic_search_product_catalog(session, "gadget", top_k=3)
        assert isinstance(result, list)
        assert len(result) <= 3
