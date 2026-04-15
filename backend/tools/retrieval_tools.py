"""
Predefined, role-scoped query functions for the Retrieval Agent.
Each function enforces column-level and row-level access control
matching the role-based business rules enforced by the harness.

All functions accept a SQLAlchemy Session and return lists of dicts.
UUID IDs are returned as strings for JSON serialization.
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.models import (
    Product,
    Customer,
    Order,
    Supplier,
    SupplierProduct,
    Partner,
    PartnerAgreement,
    PartnerProductRelation,
)

# ─── CUSTOMER TOOLS ──────────────────────────────────────────────


def get_product_catalog(session: Session) -> list[dict[str, Any]]:
    """Get the product catalog with name, description, selling price, stock, link, and category."""
    rows = session.query(
        Product.id,
        Product.name,
        Product.description,
        Product.selling_price,  # Exclude cost price
        Product.stock_number,
        Product.product_link,
        Product.category,
    ).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "selling_price": float(r.selling_price) if r.selling_price else 0.0,
            "stock_number": r.stock_number,
            "product_link": r.product_link,
            "category": r.category,
        }
        for r in rows
    ]


def get_customer_orders(session: Session, customer_id: str) -> list[dict[str, Any]]:
    """Get all orders for a specific customer, including product name and order status."""
    rows = (
        session.query(
            Order.id,
            Order.quantity,
            Order.total_price,
            Order.order_date,
            Order.status,
            Order.channel,
            Product.name.label("product_name"),
        )
        .join(Product, Order.product_id == Product.id)
        .filter(Order.customer_id == uuid.UUID(customer_id))
        .all()
    )
    return [
        {
            "order_id": str(r.id),
            "product_name": r.product_name,
            "quantity": r.quantity,
            "total_price": float(r.total_price),
            "order_date": str(r.order_date),
            "status": r.status,
            "channel": r.channel,
        }
        for r in rows
    ]


def get_customer_profile(session: Session, customer_id: str) -> dict[str, Any] | None:
    """Get a customer's own profile information."""
    c = (
        session.query(
            Customer.id,
            Customer.name,
            Customer.email,
            Customer.phone,
            Customer.company,
            Customer.status,
            Customer.preference,
        )
        .filter(Customer.id == uuid.UUID(customer_id))
        .first()
    )
    if not c:
        return None
    return {
        "id": str(c.id),
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "company": c.company,
        "status": c.status,
        "preference": c.preference,
    }


# ─── SUPPLIER TOOLS ──────────────────────────────────────────────


def get_supplier_profile(session: Session, supplier_id: str) -> dict[str, Any] | None:
    """Get a supplier's own profile information."""
    s = (
        session.query(
            Supplier.id,
            Supplier.name,
            Supplier.email,
            Supplier.phone,
            Supplier.category,
            Supplier.contract_notes,
        )
        .filter(Supplier.id == uuid.UUID(supplier_id))
        .first()
    )
    if not s:
        return None
    return {
        "id": str(s.id),
        "name": s.name,
        "email": s.email,
        "phone": s.phone,
        "category": s.category,
        "contract_notes": s.contract_notes,
    }


def get_supplier_contracts(session: Session, supplier_id: str) -> list[dict[str, Any]]:
    """Get all supply contracts for a specific supplier, including product details."""
    rows = (
        session.query(
            SupplierProduct.id,
            SupplierProduct.supply_price,
            SupplierProduct.stock_we_buy,
            SupplierProduct.lead_time_days,
            SupplierProduct.contract_start,
            SupplierProduct.contract_end,
            SupplierProduct.is_active,
            SupplierProduct.notes,
            Product.name.label("product_name"),
            Product.description.label("product_description"),
            Product.stock_number,
        )
        .join(Product, SupplierProduct.product_id == Product.id)
        .filter(SupplierProduct.supplier_id == uuid.UUID(supplier_id))
        .all()
    )
    return [
        {
            "contract_id": str(r.id),
            "product_name": r.product_name,
            "product_description": r.product_description,
            "supply_price": float(r.supply_price) if r.supply_price else 0.0,
            "stock_number": r.stock_number,
            "stock_we_buy": r.stock_we_buy,
            "lead_time_days": r.lead_time_days,
            "contract_start": str(r.contract_start) if r.contract_start else None,
            "contract_end": str(r.contract_end) if r.contract_end else None,
            "is_active": r.is_active,
            "notes": r.notes,
        }
        for r in rows
    ]


def get_product_stock(session: Session) -> list[dict[str, Any]]:
    """Get product stock levels — name, description, and current stock quantity only."""
    rows = session.query(
        Product.id,
        Product.name,
        Product.description,
        Product.stock_number,
    ).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "stock_number": r.stock_number,
        }
        for r in rows
    ]


def evaluate_discount_request(
    session: Session,
    product_query: str,
    quantity: int,
    requested_discount_pct: float | None = None,
) -> dict[str, Any]:
    """Internal pricing guidance for discount negotiation. Returns safe negotiation data, including cost-aware thresholds for internal use only."""
    normalized_query = f"%{product_query.strip()}%"
    product = (
        session.query(Product)
        .filter(
            (Product.name.ilike(normalized_query)) | (Product.description.ilike(normalized_query))
        )
        .order_by(Product.name.asc())
        .first()
    )

    if not product:
        semantic_matches = semantic_search_full_product_table(session, product_query, top_k=1)
        if not semantic_matches:
            return {
                "status": "not_found",
                "reason": "No matching product found for discount evaluation.",
            }
        matched_id = semantic_matches[0]["id"]
        product = session.query(Product).filter(Product.id == matched_id).first()

    if not product:
        return {
            "status": "not_found",
            "reason": "No matching product found for discount evaluation.",
        }

    sell = float(product.selling_price) if product.selling_price else 0.0
    cost = float(product.cost_price) if product.cost_price else 0.0
    stock = int(product.stock_number or 0)
    requested = float(requested_discount_pct or 0.0)

    if quantity >= 100:
        policy_band = 0.0
        policy_requires_approval = True
    elif quantity >= 50:
        policy_band = 15.0
        policy_requires_approval = False
    elif quantity >= 10:
        policy_band = 10.0
        policy_requires_approval = False
    else:
        policy_band = 0.0
        policy_requires_approval = False

    margin_floor_price = cost * 1.12
    if sell > 0:
        margin_safe_discount = max(0.0, round((1 - (margin_floor_price / sell)) * 100, 2))
    else:
        margin_safe_discount = 0.0

    max_discount_pct = round(min(policy_band, margin_safe_discount), 2)
    recommended_discount_pct = max_discount_pct if quantity >= 10 else 0.0

    approval_required = policy_requires_approval or requested > max_discount_pct or quantity > stock
    discounted_unit_price = round(
        sell * (1 - (min(requested or recommended_discount_pct, 100) / 100)), 2
    )

    customer_safe_summary = (
        f"For {quantity} units of {product.name}, the business can discuss up to {recommended_discount_pct:.2f}% "
        f"without owner approval if stock is available. Larger concessions require approval."
    )

    return {
        "status": "ok",
        "product_id": str(product.id),
        "product_name": product.name,
        "quantity": quantity,
        "stock_available": stock,
        "selling_price": round(sell, 2),
        "cost_price": round(cost, 2),
        "requested_discount_pct": round(requested, 2),
        "max_discount_pct": max_discount_pct,
        "recommended_discount_pct": recommended_discount_pct,
        "approval_required": approval_required,
        "discounted_unit_price": discounted_unit_price,
        "customer_safe_summary": customer_safe_summary,
        "reason": (
            "Requested discount exceeds policy or margin threshold."
            if approval_required and requested > max_discount_pct
            else "Discount can be negotiated within current quantity and margin thresholds."
        ),
    }


# ─── INVESTOR TOOLS ──────────────────────────────────────────────


def get_full_product_table(session: Session) -> list[dict[str, Any]]:
    """Get the full product table including cost price and margins."""
    rows = session.query(Product).all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "selling_price": float(r.selling_price) if r.selling_price else 0.0,
            "cost_price": float(r.cost_price) if r.cost_price else 0.0,
            "margin": float((r.selling_price or 0) - (r.cost_price or 0)),
            "stock_number": r.stock_number,
            "category": r.category,
            "product_link": r.product_link,
        }
        for r in rows
    ]


def get_all_orders(session: Session) -> list[dict[str, Any]]:
    """Get all orders across all customers with product and customer info."""
    rows = (
        session.query(
            Order.id,
            Order.quantity,
            Order.total_price,
            Order.order_date,
            Order.status,
            Order.channel,
            Product.name.label("product_name"),
            Customer.name.label("customer_name"),
        )
        .join(Product, Order.product_id == Product.id)
        .join(Customer, Order.customer_id == Customer.id)
        .all()
    )
    return [
        {
            "order_id": str(r.id),
            "product_name": r.product_name,
            "customer_name": r.customer_name,
            "quantity": r.quantity,
            "total_price": float(r.total_price),
            "order_date": str(r.order_date),
            "status": r.status,
            "channel": r.channel,
        }
        for r in rows
    ]


def get_customer_count(session: Session) -> dict[str, Any]:
    """Get the total number of customers (aggregate only)."""
    count = session.query(func.count(Customer.id)).scalar()
    return {"total_customers": count}


def get_supply_overview(session: Session) -> list[dict[str, Any]]:
    """Get full supply contract table for investor analysis."""
    rows = (
        session.query(
            SupplierProduct.id,
            SupplierProduct.supply_price,
            SupplierProduct.stock_we_buy,
            SupplierProduct.lead_time_days,
            SupplierProduct.contract_start,
            SupplierProduct.contract_end,
            SupplierProduct.is_active,
            Supplier.name.label("supplier_name"),
            Product.name.label("product_name"),
            Product.selling_price,
        )
        .join(Supplier, SupplierProduct.supplier_id == Supplier.id)
        .join(Product, SupplierProduct.product_id == Product.id)
        .all()
    )
    return [
        {
            "contract_id": str(r.id),
            "supplier_name": r.supplier_name,
            "product_name": r.product_name,
            "supply_price": float(r.supply_price) if r.supply_price else 0.0,
            "selling_price": float(r.selling_price) if r.selling_price else 0.0,
            "stock_we_buy": r.stock_we_buy,
            "lead_time_days": r.lead_time_days,
            "contract_start": str(r.contract_start) if r.contract_start else None,
            "contract_end": str(r.contract_end) if r.contract_end else None,
            "is_active": r.is_active,
        }
        for r in rows
    ]


def get_product_roi(session: Session) -> list[dict[str, Any]]:
    """Compute per-product ROI: cost, selling price, margin, total units sold, total revenue, and ROI percentage."""
    rows = (
        session.query(
            Product.id,
            Product.name,
            Product.description,
            Product.cost_price,
            Product.selling_price,
            func.coalesce(func.sum(Order.quantity), 0).label("total_sold"),
            func.coalesce(func.sum(Order.total_price), 0).label("total_revenue"),
        )
        .outerjoin(Order, Product.id == Order.product_id)
        .group_by(Product.id)
        .all()
    )
    results = []
    for r in rows:
        cost = float(r.cost_price) if r.cost_price else 0.0
        sell = float(r.selling_price) if r.selling_price else 0.0
        margin = sell - cost
        roi_pct = (margin / cost * 100) if cost > 0 else 0.0
        results.append(
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "cost_price": cost,
                "selling_price": sell,
                "margin": margin,
                "roi_pct": round(roi_pct, 2),
                "total_sold": int(r.total_sold),
                "total_revenue": float(r.total_revenue),
            }
        )
    return results


def get_sales_stats(session: Session) -> dict[str, Any]:
    """Get aggregate sales statistics: total orders, total revenue, average order value, orders by status."""
    total_orders = session.query(func.count(Order.id)).scalar()
    total_revenue = float(session.query(func.coalesce(func.sum(Order.total_price), 0)).scalar())
    avg_order = float(session.query(func.coalesce(func.avg(Order.total_price), 0)).scalar())

    status_rows = session.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    by_status = {status: count for status, count in status_rows}

    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "avg_order_value": round(avg_order, 2),
        "orders_by_status": by_status,
    }


# ─── PARTNER TOOLS ───────────────────────────────────────────────


def get_partner_profile(session: Session, partner_id: str) -> dict[str, Any] | None:
    """Get a partner's own profile information."""
    p = (
        session.query(
            Partner.id,
            Partner.name,
            Partner.email,
            Partner.phone,
            Partner.partner_type,
        )
        .filter(Partner.id == uuid.UUID(partner_id))
        .first()
    )
    if not p:
        return None
    return {
        "id": str(p.id),
        "name": p.name,
        "email": p.email,
        "phone": p.phone,
        "partner_type": p.partner_type,
    }


def get_partner_agreements(session: Session, partner_id: str) -> list[dict[str, Any]]:
    """Get all agreements for a specific partner."""
    rows = (
        session.query(PartnerAgreement)
        .filter(PartnerAgreement.partner_id == uuid.UUID(partner_id))
        .all()
    )
    return [
        {
            "agreement_id": str(r.id),
            "description": r.description,
            "agreement_type": r.agreement_type,
            "revenue_share_pct": float(r.revenue_share_pct) if r.revenue_share_pct else None,
            "start_date": str(r.start_date) if r.start_date else None,
            "end_date": str(r.end_date) if r.end_date else None,
            "is_active": r.is_active,
            "notes": r.notes,
        }
        for r in rows
    ]


def get_partner_products(session: Session, partner_id: str) -> list[dict[str, Any]]:
    """Get all products linked to a specific partner, with product details."""
    rows = (
        session.query(
            PartnerProductRelation.id,
            Product.name.label("product_name"),
            Product.description.label("product_description"),
            Product.selling_price,
        )
        .join(Product, PartnerProductRelation.product_id == Product.id)
        .filter(PartnerProductRelation.partner_id == uuid.UUID(partner_id))
        .all()
    )
    return [
        {
            "id": str(r.id),
            "product_name": r.product_name,
            "product_description": r.product_description,
            "selling_price": float(r.selling_price) if r.selling_price else 0.0,
        }
        for r in rows
    ]


# ─── SEMANTIC SEARCH TOOLS ────────────────────────────────────────────────────


def _embed_query(query: str) -> list[float]:
    """Embed a query string using the configured embedding model."""
    embedder = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        api_key=SecretStr(settings.OPENAI_API_KEY),
    )
    return embedder.embed_query(query)


def semantic_search_product_catalog(
    session: Session,
    query: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Find products semantically similar to the query. Returns catalog fields (no cost price)."""
    k = top_k or settings.BUSINESS_TOP_K
    query_vector = _embed_query(query)
    distance_expr = Product.description_embedding.cosine_distance(query_vector)
    rows = (
        session.query(Product, distance_expr.label("distance"))
        .filter(Product.description_embedding.isnot(None))
        .order_by(distance_expr)
        .limit(k)
        .all()
    )
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "selling_price": float(p.selling_price) if p.selling_price else 0.0,
            "stock_number": p.stock_number,
            "product_link": p.product_link,
            "category": p.category,
            "similarity_score": round(1.0 - distance, 4),
        }
        for p, distance in rows
    ]


def semantic_search_full_product_table(
    session: Session,
    query: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Find products semantically similar to the query. Returns full table including cost price (investor only)."""
    k = top_k or settings.BUSINESS_TOP_K
    query_vector = _embed_query(query)
    distance_expr = Product.description_embedding.cosine_distance(query_vector)
    rows = (
        session.query(Product, distance_expr.label("distance"))
        .filter(Product.description_embedding.isnot(None))
        .order_by(distance_expr)
        .limit(k)
        .all()
    )
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "selling_price": float(p.selling_price) if p.selling_price else 0.0,
            "cost_price": float(p.cost_price) if p.cost_price else 0.0,
            "margin": float((p.selling_price or 0) - (p.cost_price or 0)),
            "stock_number": p.stock_number,
            "category": p.category,
            "product_link": p.product_link,
            "similarity_score": round(1.0 - distance, 4),
        }
        for p, distance in rows
    ]


def semantic_search_supplier_contracts(
    session: Session,
    query: str,
    supplier_id: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Find supply contracts semantically similar to the query, scoped to a supplier."""
    k = top_k or settings.BUSINESS_TOP_K
    query_vector = _embed_query(query)
    distance_expr = SupplierProduct.notes_embedding.cosine_distance(query_vector)
    rows = (
        session.query(SupplierProduct, Product, distance_expr.label("distance"))
        .join(Product, SupplierProduct.product_id == Product.id)
        .filter(
            SupplierProduct.supplier_id == uuid.UUID(supplier_id),
            SupplierProduct.notes_embedding.isnot(None),
        )
        .order_by(distance_expr)
        .limit(k)
        .all()
    )
    return [
        {
            "contract_id": str(c.id),
            "product_name": p.name,
            "product_description": p.description,
            "supply_price": float(c.supply_price) if c.supply_price else 0.0,
            "stock_number": p.stock_number,
            "stock_we_buy": c.stock_we_buy,
            "lead_time_days": c.lead_time_days,
            "contract_start": str(c.contract_start) if c.contract_start else None,
            "contract_end": str(c.contract_end) if c.contract_end else None,
            "is_active": c.is_active,
            "notes": c.notes,
            "similarity_score": round(1.0 - distance, 4),
        }
        for c, p, distance in rows
    ]


def semantic_search_supply_overview(
    session: Session,
    query: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Find supply contracts semantically similar to the query. Returns full supply overview (investor only)."""
    k = top_k or settings.BUSINESS_TOP_K
    query_vector = _embed_query(query)
    distance_expr = SupplierProduct.notes_embedding.cosine_distance(query_vector)
    rows = (
        session.query(SupplierProduct, Supplier, Product, distance_expr.label("distance"))
        .join(Supplier, SupplierProduct.supplier_id == Supplier.id)
        .join(Product, SupplierProduct.product_id == Product.id)
        .filter(SupplierProduct.notes_embedding.isnot(None))
        .order_by(distance_expr)
        .limit(k)
        .all()
    )
    return [
        {
            "contract_id": str(c.id),
            "supplier_name": s.name,
            "product_name": p.name,
            "supply_price": float(c.supply_price) if c.supply_price else 0.0,
            "selling_price": float(p.selling_price) if p.selling_price else 0.0,
            "stock_we_buy": c.stock_we_buy,
            "lead_time_days": c.lead_time_days,
            "contract_start": str(c.contract_start) if c.contract_start else None,
            "contract_end": str(c.contract_end) if c.contract_end else None,
            "is_active": c.is_active,
            "similarity_score": round(1.0 - distance, 4),
        }
        for c, s, p, distance in rows
    ]


def semantic_search_all_partner_agreements(
    session: Session,
    query: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Find partner agreements semantically similar to the query across all partners (investor only)."""
    k = top_k or settings.BUSINESS_TOP_K
    query_vector = _embed_query(query)
    distance_expr = PartnerAgreement.description_embedding.cosine_distance(query_vector)
    rows = (
        session.query(PartnerAgreement, Partner, distance_expr.label("distance"))
        .join(Partner, PartnerAgreement.partner_id == Partner.id)
        .filter(PartnerAgreement.description_embedding.isnot(None))
        .order_by(distance_expr)
        .limit(k)
        .all()
    )
    return [
        {
            "agreement_id": str(a.id),
            "partner_name": prt.name,
            "description": a.description,
            "agreement_type": a.agreement_type,
            "revenue_share_pct": float(a.revenue_share_pct) if a.revenue_share_pct else None,
            "start_date": str(a.start_date) if a.start_date else None,
            "end_date": str(a.end_date) if a.end_date else None,
            "is_active": a.is_active,
            "similarity_score": round(1.0 - distance, 4),
        }
        for a, prt, distance in rows
    ]


def semantic_search_partner_agreements(
    session: Session,
    query: str,
    partner_id: str,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Find partner agreements semantically similar to the query, scoped to a partner."""
    k = top_k or settings.BUSINESS_TOP_K
    query_vector = _embed_query(query)
    distance_expr = PartnerAgreement.description_embedding.cosine_distance(query_vector)
    rows = (
        session.query(PartnerAgreement, distance_expr.label("distance"))
        .filter(
            PartnerAgreement.partner_id == uuid.UUID(partner_id),
            PartnerAgreement.description_embedding.isnot(None),
        )
        .order_by(distance_expr)
        .limit(k)
        .all()
    )
    return [
        {
            "agreement_id": str(a.id),
            "description": a.description,
            "agreement_type": a.agreement_type,
            "revenue_share_pct": float(a.revenue_share_pct) if a.revenue_share_pct else None,
            "start_date": str(a.start_date) if a.start_date else None,
            "end_date": str(a.end_date) if a.end_date else None,
            "is_active": a.is_active,
            "notes": a.notes,
            "similarity_score": round(1.0 - distance, 4),
        }
        for a, distance in rows
    ]
