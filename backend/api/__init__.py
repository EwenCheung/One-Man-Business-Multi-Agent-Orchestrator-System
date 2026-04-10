"""
API package — FastAPI routes.
"""

from datetime import date
import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.db.engine import SessionLocal
from backend.db.models import Customer, Order, Product

purchase_router = APIRouter(tags=["orders"])
logger = logging.getLogger(__name__)


class PurchaseOrderInput(BaseModel):
    owner_id: str
    customer_id: str
    product_id: str
    quantity: int
    order_id: str
    order_date: str
    channel: str = "website"


def _is_internal_request(request: Request) -> bool:
    provided_key = request.headers.get("X-Internal-Api-Key", "")
    configured_key = (request.app.state.internal_api_key or "").strip()
    if configured_key:
        import hmac

        return bool(provided_key) and hmac.compare_digest(provided_key, configured_key)
    return str(request.app.state.app_env).lower() == "development"


def _require_internal_request(request: Request) -> None:
    if not _is_internal_request(request):
        raise HTTPException(status_code=403, detail="Forbidden")


def _create_customer_purchase(payload: PurchaseOrderInput) -> dict[str, object]:
    if payload.quantity < 1:
        raise HTTPException(status_code=400, detail="Invalid purchase request")

    try:
        owner_uuid = uuid.UUID(payload.owner_id)
        customer_uuid = uuid.UUID(payload.customer_id)
        product_uuid = uuid.UUID(payload.product_id)
        order_uuid = uuid.UUID(payload.order_id)
        order_date_value = date.fromisoformat(payload.order_date)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid purchase request") from exc

    session = SessionLocal()
    try:
        customer = (
            session.query(Customer)
            .filter(Customer.id == customer_uuid, Customer.owner_id == owner_uuid)
            .one_or_none()
        )
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        product = (
            session.query(Product)
            .filter(Product.id == product_uuid, Product.owner_id == owner_uuid)
            .with_for_update()
            .one_or_none()
        )
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")

        current_stock = int(product.stock_number or 0)
        if current_stock < payload.quantity:
            raise HTTPException(status_code=400, detail="Out of stock")

        product.stock_number = current_stock - payload.quantity
        total_price = (product.selling_price or 0) * payload.quantity

        order = Order(
            id=order_uuid,
            owner_id=owner_uuid,
            customer_id=customer_uuid,
            product_id=product_uuid,
            quantity=payload.quantity,
            total_price=total_price,
            order_date=order_date_value,
            status="paid",
            channel=payload.channel,
        )
        session.add(order)
        session.commit()

        return {
            "order_id": str(order.id),
            "total_price": float(total_price),
            "remaining_stock": product.stock_number,
        }
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        logger.error("Failed to create customer purchase: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create order") from exc
    finally:
        session.close()


@purchase_router.post("/orders/purchase")
def create_customer_purchase(payload: PurchaseOrderInput, request: Request):
    _require_internal_request(request)
    purchase = _create_customer_purchase(payload)
    return {"success": True, "purchase": purchase}


__all__ = ["purchase_router"]
