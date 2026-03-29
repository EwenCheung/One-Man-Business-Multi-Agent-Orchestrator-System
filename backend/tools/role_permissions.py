"""
Hard enforcement layer that maps each sender role to the specific
retrieval tool functions they are permitted to use. The retrieval
agent must consult this mapping before binding tools to the LLM.
"""

from backend.tools.retrieval_tools import (
    # Customer
    get_product_catalog,
    get_customer_orders,
    get_customer_profile,
    # Supplier
    get_supplier_profile,
    get_supplier_contracts,
    get_product_stock,
    # Investor
    get_full_product_table,
    get_all_orders,
    get_customer_count,
    get_supply_overview,
    get_product_roi,
    get_sales_stats,
    # Partner
    get_partner_profile,
    get_partner_agreements,
    get_partner_products,
    # Semantic search — customer / supplier / partner
    semantic_search_product_catalog,
    # Semantic search — supplier
    semantic_search_supplier_contracts,
    # Semantic search — investor
    semantic_search_full_product_table,
    semantic_search_supply_overview,
    semantic_search_all_partner_agreements,
    # Semantic search — partner
    semantic_search_partner_agreements,
)

ROLE_TOOL_MAP: dict[str, list] = {
    "customer": [
        get_product_catalog,
        get_customer_orders,
        get_customer_profile,
        semantic_search_product_catalog,
    ],
    "supplier": [
        get_supplier_profile,
        get_supplier_contracts,
        get_product_stock,
        semantic_search_product_catalog,
        semantic_search_supplier_contracts,
    ],
    "investor": [
        get_full_product_table,
        get_all_orders,
        get_customer_count,
        get_supply_overview,
        get_product_roi,
        get_sales_stats,
        semantic_search_full_product_table,
        semantic_search_supply_overview,
        semantic_search_all_partner_agreements,
    ],
    "partner": [
        get_partner_profile,
        get_partner_agreements,
        get_partner_products,
        semantic_search_product_catalog,
        semantic_search_partner_agreements,
    ],
}


def get_tools_for_role(role: str) -> list:
    """
    Return the list of allowed tool functions for a given role.

    Raises ValueError if the role is not recognized.
    """
    role = role.lower()
    if role not in ROLE_TOOL_MAP:
        raise ValueError(f"Unknown role: {role!r}. Must be one of {list(ROLE_TOOL_MAP.keys())}")
    return ROLE_TOOL_MAP[role]
