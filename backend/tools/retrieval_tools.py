"""
Predefined, role-scoped query functions for the Retrieval Agent.
Each function enforces column-level and row-level access control
matching the Role-Based Access rules defined in README.md.

All functions accept a SQLAlchemy Session and return lists of dicts.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.orm_models import (
    Product, Customer, Order,
    Supplier, SupplyContract,
    Partner, PartnerAgreement, PartnerProduct,
)

#─── CUSTOMER TOOLS ──────────────────────────────────────────────

def get_product_catalog(session: Session) -> list[dict]:
    """Get the product catalog with name, description, selling price, stock, link, and category."""
    rows = session.query(
        Product.id,
        Product.name,
        Product.description,
        Product.selling_price, # Exclude cost price
        Product.stock_quantity,
        Product.link,
        Product.category,
    ).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "selling_price": float(r.selling_price),
            "stock_quantity": r.stock_quantity,
            "link": r.link,
            "category": r.category,
        }
        for r in rows
    ]


def get_customer_orders(session: Session, customer_id: int) -> list[dict]:
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
        .filter(Order.customer_id == customer_id)
        .all()
    )
    return [
        {
            "order_id": r.id,
            "product_name": r.product_name,
            "quantity": r.quantity,
            "total_price": float(r.total_price),
            "order_date": str(r.order_date),
            "status": r.status,
            "channel": r.channel,
        }
        for r in rows
    ]


def get_customer_profile(session: Session, customer_id: int) -> dict | None:
    """Get a customer's own profile information."""
    c = session.query(
        Customer.id,
        Customer.name,
        Customer.email,
        Customer.phone,
        Customer.address,
        Customer.platform,
    ).filter(Customer.id == customer_id).first()
    if not c:
        return None
    return {
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "address": c.address,
        "platform": c.platform,
    }


# ─── SUPPLIER TOOLS ──────────────────────────────────────────────

def get_supplier_profile(session: Session, supplier_id: int) -> dict | None:
    """Get a supplier's own profile information."""
    s = session.query(
        Supplier.id,
        Supplier.name,
        Supplier.contact_person,
        Supplier.email,
        Supplier.phone,
    ).filter(Supplier.id == supplier_id).first()
    if not s:
        return None
    return {
        "id": s.id,
        "name": s.name,
        "contact_person": s.contact_person,
        "email": s.email,
        "phone": s.phone,
    }


def get_supplier_contracts(session: Session, supplier_id: int) -> list[dict]:
    """Get all supply contracts for a specific supplier, including product details."""
    rows = (
        session.query(
            SupplyContract.id,
            SupplyContract.supply_price,
            SupplyContract.total_order_qty,
            SupplyContract.lead_time_days,
            SupplyContract.contract_start,
            SupplyContract.contract_end,
            SupplyContract.is_active,
            SupplyContract.notes,
            Product.name.label("product_name"),
            Product.description.label("product_description"),
            Product.stock_quantity,
        )
        .join(Product, SupplyContract.product_id == Product.id)
        .filter(SupplyContract.supplier_id == supplier_id)
        .all()
    )
    return [
        {
            "contract_id": r.id,
            "product_name": r.product_name,
            "product_description": r.product_description,
            "supply_price": float(r.supply_price),
            "stock_quantity": r.stock_quantity,
            "total_order_qty": r.total_order_qty,
            "lead_time_days": r.lead_time_days,
            "contract_start": str(r.contract_start),
            "contract_end": str(r.contract_end) if r.contract_end else None,
            "is_active": r.is_active,
            "notes": r.notes,
        }
        for r in rows
    ]


def get_product_stock(session: Session) -> list[dict]:
    """Get product stock levels — name, description, and current stock quantity only."""
    rows = session.query(
        Product.id,
        Product.name,
        Product.description,
        Product.stock_quantity,
    ).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "stock_quantity": r.stock_quantity,
        }
        for r in rows
    ]


# ─── INVESTOR TOOLS ──────────────────────────────────────────────

def get_full_product_table(session: Session) -> list[dict]:
    """Get the full product table including cost price and margins."""
    rows = session.query(Product).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "selling_price": float(r.selling_price),
            "cost_price": float(r.cost_price),
            "margin": float(r.selling_price - r.cost_price),
            "stock_quantity": r.stock_quantity,
            "category": r.category,
            "link": r.link,
        }
        for r in rows
    ]


def get_all_orders(session: Session) -> list[dict]:
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
            "order_id": r.id,
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


def get_customer_count(session: Session) -> dict:
    """Get the total number of customers (aggregate only)."""
    count = session.query(func.count(Customer.id)).scalar()
    return {"total_customers": count}


def get_supply_overview(session: Session) -> list[dict]:
    """Get full supply contract table for investor analysis."""
    rows = (
        session.query(
            SupplyContract.id,
            SupplyContract.supply_price,
            SupplyContract.total_order_qty,
            SupplyContract.lead_time_days,
            SupplyContract.contract_start,
            SupplyContract.contract_end,
            SupplyContract.is_active,
            Supplier.name.label("supplier_name"),
            Product.name.label("product_name"),
            Product.selling_price,
        )
        .join(Supplier, SupplyContract.supplier_id == Supplier.id)
        .join(Product, SupplyContract.product_id == Product.id)
        .all()
    )
    return [
        {
            "contract_id": r.id,
            "supplier_name": r.supplier_name,
            "product_name": r.product_name,
            "supply_price": float(r.supply_price),
            "selling_price": float(r.selling_price),
            "total_order_qty": r.total_order_qty,
            "lead_time_days": r.lead_time_days,
            "contract_start": str(r.contract_start),
            "contract_end": str(r.contract_end) if r.contract_end else None,
            "is_active": r.is_active,
        }
        for r in rows
    ]


def get_product_roi(session: Session) -> list[dict]:
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
        cost = float(r.cost_price)
        sell = float(r.selling_price)
        margin = sell - cost
        roi_pct = (margin / cost * 100) if cost > 0 else 0.0
        results.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "cost_price": cost,
            "selling_price": sell,
            "margin": margin,
            "roi_pct": round(roi_pct, 2),
            "total_sold": int(r.total_sold),
            "total_revenue": float(r.total_revenue),
        })
    return results


def get_sales_stats(session: Session) -> dict:
    """Get aggregate sales statistics: total orders, total revenue, average order value, orders by status."""
    total_orders = session.query(func.count(Order.id)).scalar()
    total_revenue = float(session.query(func.coalesce(func.sum(Order.total_price), 0)).scalar())
    avg_order = float(session.query(func.coalesce(func.avg(Order.total_price), 0)).scalar())

    status_rows = (
        session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )
    by_status = {status: count for status, count in status_rows}

    return {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "avg_order_value": round(avg_order, 2),
        "orders_by_status": by_status,
    }


# ─── PARTNER TOOLS ───────────────────────────────────────────────

def get_partner_profile(session: Session, partner_id: int) -> dict | None:
    """Get a partner's own profile information."""
    p = session.query(
        Partner.id,
        Partner.name,
        Partner.contact_person,
        Partner.email,
        Partner.phone,
    ).filter(Partner.id == partner_id).first()
    if not p:
        return None
    return {
        "id": p.id,
        "name": p.name,
        "contact_person": p.contact_person,
        "email": p.email,
        "phone": p.phone,
    }


def get_partner_agreements(session: Session, partner_id: int) -> list[dict]:
    """Get all agreements for a specific partner."""
    rows = (
        session.query(PartnerAgreement)
        .filter(PartnerAgreement.partner_id == partner_id)
        .all()
    )
    return [
        {
            "agreement_id": r.id,
            "description": r.description,
            "agreement_type": r.agreement_type,
            "revenue_share_pct": float(r.revenue_share_pct) if r.revenue_share_pct else None,
            "start_date": str(r.start_date),
            "end_date": str(r.end_date) if r.end_date else None,
            "is_active": r.is_active,
            "notes": r.notes,
        }
        for r in rows
    ]


def get_partner_products(session: Session, partner_id: int) -> list[dict]:
    """Get all products linked to a specific partner, with product details and agreement info."""
    rows = (
        session.query(
            PartnerProduct.id,
            Product.name.label("product_name"),
            Product.description.label("product_description"),
            Product.selling_price,                            # Exclude cost price
            PartnerAgreement.agreement_type,
            PartnerAgreement.id.label("agreement_id"),
        )
        .join(Product, PartnerProduct.product_id == Product.id)
        .join(PartnerAgreement, PartnerProduct.agreement_id == PartnerAgreement.id)
        .filter(PartnerProduct.partner_id == partner_id)
        .all()
    )
    return [
        {
            "id": r.id,
            "product_name": r.product_name,
            "product_description": r.product_description,
            "selling_price": float(r.selling_price),
            "agreement_id": r.agreement_id,
            "agreement_type": r.agreement_type,
        }
        for r in rows
    ]