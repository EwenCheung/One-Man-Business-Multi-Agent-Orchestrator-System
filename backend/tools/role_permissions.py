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
)

ROLE_TOOL_MAP: dict[str, list] = {
    "customer": [
        get_product_catalog,
        get_customer_orders,
        get_customer_profile,
    ],
    "supplier": [
        get_supplier_profile,
        get_supplier_contracts,
        get_product_stock,
    ],
    "investor": [
        get_full_product_table,
        get_all_orders,
        get_customer_count,
        get_supply_overview,
        get_product_roi,
        get_sales_stats,
    ],
    "partner": [
        get_partner_profile,
        get_partner_agreements,
        get_partner_products,
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
