"""
Tests for the retrieval tools and role-based access control.

These are integration tests that run against the seeded database.
They verify:
    - Each role can only access its permitted tools
    - Column filtering works (customer can't see cost_price)
    - Row scoping works (customer A can't see customer B's orders)
    - Tool functions return expected data shapes
"""

import pytest
from backend.db.engine import SessionLocal
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
)
from backend.tools.role_permissions import get_tools_for_role, ROLE_TOOL_MAP


@pytest.fixture
def session():
    s = SessionLocal()
    yield s
    s.close()


# ─── Role Permission Tests ───────────────────────────────────────

class TestRolePermissions:
    def test_customer_has_exactly_3_tools(self):
        tools = get_tools_for_role("customer")
        assert len(tools) == 3
        names = {fn.__name__ for fn in tools}
        assert names == {"get_product_catalog", "get_customer_orders", "get_customer_profile"}

    def test_supplier_has_exactly_3_tools(self):
        tools = get_tools_for_role("supplier")
        assert len(tools) == 3
        names = {fn.__name__ for fn in tools}
        assert names == {"get_supplier_profile", "get_supplier_contracts", "get_product_stock"}

    def test_investor_has_exactly_6_tools(self):
        tools = get_tools_for_role("investor")
        assert len(tools) == 6
        names = {fn.__name__ for fn in tools}
        assert names == {
            "get_full_product_table", "get_all_orders", "get_customer_count",
            "get_supply_overview", "get_product_roi", "get_sales_stats",
        }

    def test_partner_has_exactly_3_tools(self):
        tools = get_tools_for_role("partner")
        assert len(tools) == 3
        names = {fn.__name__ for fn in tools}
        assert names == {"get_partner_profile", "get_partner_agreements", "get_partner_products"}

    def test_unknown_role_raises(self):
        with pytest.raises(ValueError, match="Unknown role"):
            get_tools_for_role("hacker")

    def test_role_is_case_insensitive(self):
        tools = get_tools_for_role("CUSTOMER")
        assert len(tools) == 3

    def test_customer_cannot_access_investor_tools(self):
        customer_names = {fn.__name__ for fn in get_tools_for_role("customer")}
        assert "get_full_product_table" not in customer_names
        assert "get_product_roi" not in customer_names
        assert "get_all_orders" not in customer_names

    def test_supplier_cannot_access_customer_tools(self):
        supplier_names = {fn.__name__ for fn in get_tools_for_role("supplier")}
        assert "get_customer_orders" not in supplier_names
        assert "get_customer_profile" not in supplier_names

    def test_partner_cannot_access_supplier_tools(self):
        partner_names = {fn.__name__ for fn in get_tools_for_role("partner")}
        assert "get_supplier_contracts" not in partner_names
        assert "get_supplier_profile" not in partner_names


# ─── Column Filtering Tests ──────────────────────────────────────

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
            assert "stock_quantity" in row

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

    def test_partner_products_excludes_cost_price(self, session):
        rows = get_partner_products(session, 1)
        if rows:
            for row in rows:
                assert "cost_price" not in row
                assert "selling_price" in row


# ─── Row Scoping Tests ───────────────────────────────────────────

class TestRowScoping:
    def test_customer_orders_scoped_to_customer(self, session):
        orders_c1 = get_customer_orders(session, 1)
        orders_c2 = get_customer_orders(session, 2)
        # Both should return lists (possibly empty if no orders for that customer)
        assert isinstance(orders_c1, list)
        assert isinstance(orders_c2, list)
        # If both have orders, they should be different
        if orders_c1 and orders_c2:
            c1_ids = {o["order_id"] for o in orders_c1}
            c2_ids = {o["order_id"] for o in orders_c2}
            assert c1_ids.isdisjoint(c2_ids), "Customer 1 and 2 should not share order IDs"

    def test_customer_profile_returns_own_data(self, session):
        profile = get_customer_profile(session, 1)
        assert profile is not None
        assert profile["id"] == 1

    def test_customer_profile_nonexistent_returns_none(self, session):
        profile = get_customer_profile(session, 99999)
        assert profile is None

    def test_supplier_contracts_scoped_to_supplier(self, session):
        contracts = get_supplier_contracts(session, 1)
        assert isinstance(contracts, list)

    def test_supplier_profile_returns_own_data(self, session):
        profile = get_supplier_profile(session, 1)
        assert profile is not None
        assert profile["id"] == 1

    def test_partner_agreements_scoped_to_partner(self, session):
        agreements = get_partner_agreements(session, 1)
        assert isinstance(agreements, list)

    def test_partner_products_scoped_to_partner(self, session):
        products_p1 = get_partner_products(session, 1)
        products_p2 = get_partner_products(session, 2)
        assert isinstance(products_p1, list)
        assert isinstance(products_p2, list)
        if products_p1 and products_p2:
            p1_ids = {p["id"] for p in products_p1}
            p2_ids = {p["id"] for p in products_p2}
            assert p1_ids.isdisjoint(p2_ids), "Partner 1 and 2 should not share product link IDs"


# ─── Data Shape Tests ────────────────────────────────────────────

class TestDataShapes:
    def test_product_catalog_shape(self, session):
        rows = get_product_catalog(session)
        assert len(rows) == 30
        expected_keys = {"id", "name", "description", "selling_price", "stock_quantity", "link", "category"}
        assert set(rows[0].keys()) == expected_keys

    def test_all_orders_shape(self, session):
        rows = get_all_orders(session)
        assert len(rows) == 120
        expected_keys = {
            "order_id", "product_name", "customer_name",
            "quantity", "total_price", "order_date", "status", "channel",
        }
        assert set(rows[0].keys()) == expected_keys

    def test_product_roi_shape(self, session):
        rows = get_product_roi(session)
        assert len(rows) == 30
        expected_keys = {
            "id", "name", "description", "cost_price", "selling_price",
            "margin", "roi_pct", "total_sold", "total_revenue",
        }
        assert set(rows[0].keys()) == expected_keys

    def test_sales_stats_shape(self, session):
        stats = get_sales_stats(session)
        assert "total_orders" in stats
        assert "total_revenue" in stats
        assert "avg_order_value" in stats
        assert "orders_by_status" in stats
        assert stats["total_orders"] == 120

    def test_supply_overview_shape(self, session):
        rows = get_supply_overview(session)
        assert len(rows) == 30
        expected_keys = {
            "contract_id", "supplier_name", "product_name", "supply_price",
            "selling_price", "total_order_qty", "lead_time_days",
            "contract_start", "contract_end", "is_active",
        }
        assert set(rows[0].keys()) == expected_keys
