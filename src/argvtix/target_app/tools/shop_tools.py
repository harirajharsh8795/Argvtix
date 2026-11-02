"""
MCP (Model Context Protocol) style tools that the ShopOps AI agent can call.
Each tool performs a real database operation and returns structured results.
The agent calls these tools AFTER the Guard has approved the action.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from argvtix.db.models import Customer, Order, Payment, Product, Refund


@dataclass
class ToolResult:
    """Standardised result every tool returns."""

    success: bool
    data: dict
    error: str | None = None


# ---------------------------------------------------------------------------
# READ TOOLS
# ---------------------------------------------------------------------------


def get_order(db: Session, order_id: str | int) -> ToolResult:
    """
    Fetch order details including items, payment status, and current order status.
    """
    oid = str(order_id)
    order = db.get(Order, oid)
    if not order:
        return ToolResult(success=False, data={}, error=f"Order {order_id} not found")

    payment = db.query(Payment).filter(Payment.order_id == oid).first()
    refunds = db.query(Refund).filter(Refund.order_id == oid).all()

    return ToolResult(
        success=True,
        data={
            "order_id": order.id,
            "customer_id": order.customer_id,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "payment": {
                "id": payment.id if payment else None,
                "amount": float(payment.amount) if payment else None,
                "method": payment.method if payment else None,
                "status": payment.status if payment else None,
            },
            "refunds": [
                {"id": r.id, "amount": float(r.amount), "reason": r.reason} for r in refunds
            ],
        },
    )


def get_customer_balance(db: Session, customer_id: str | int) -> ToolResult:
    """
    Return customer wallet balance (sum of pending refunds + any store credit).
    In this mock implementation we treat pending refunds as "store credit".
    """
    cid = str(customer_id)
    customer = db.get(Customer, cid)
    if not customer:
        return ToolResult(success=False, data={}, error=f"Customer {customer_id} not found")

    # Pending refunds = in-flight store credit
    pending_refunds = (
        db.query(Refund).filter(Refund.customer_id == cid, Refund.status == "pending").all()
    )
    pending_amount = sum(float(r.amount) for r in pending_refunds)

    return ToolResult(
        success=True,
        data={
            "customer_id": customer.id,
            "name": customer.name,
            "email_domain": customer.email.split("@")[1] if customer.email else "masked",
            "wallet_balance": pending_amount,
            "currency": "INR",
        },
    )


def check_order_refund_status(db: Session, order_id: str | int) -> ToolResult:
    """Check if an order already has a refund processed."""
    oid = str(order_id)
    refunds = db.query(Refund).filter(Refund.order_id == oid).all()
    if not refunds:
        return ToolResult(success=True, data={"has_refund": False, "refunds": []})
    return ToolResult(
        success=True,
        data={
            "has_refund": True,
            "refunds": [
                {"id": r.id, "amount": float(r.amount), "status": r.status} for r in refunds
            ],
        },
    )


# ---------------------------------------------------------------------------
# WRITE TOOLS
# ---------------------------------------------------------------------------


def issue_refund(
    db: Session,
    customer_id: str | int,
    order_id: str | int,
    amount: float,
    reason: str = "customer_request",
    idempotency_key: str | None = None,
) -> ToolResult:
    """
    Create a new refund record for the given order.
    Atomic database-level idempotency and duplicate prevention.
    """
    oid = str(order_id)
    cid = str(customer_id)

    # 1. Check for prior refund with matching idempotency key (cross-replica protection)
    if idempotency_key:
        prior_by_key = (
            db.query(Refund).filter(Refund.idempotency_key == str(idempotency_key)).first()
        )
        if prior_by_key:
            return ToolResult(
                success=True,
                data={
                    "refund_id": prior_by_key.id,
                    "order_id": prior_by_key.order_id,
                    "amount": float(prior_by_key.amount),
                    "status": prior_by_key.status,
                    "message": f"Idempotent replay: Refund already processed (ID: {prior_by_key.id}).",
                },
            )

    order = db.get(Order, oid)
    if not order:
        return ToolResult(success=False, data={}, error=f"Order {order_id} not found")

    if str(order.customer_id) != cid:
        return ToolResult(
            success=False,
            data={},
            error="Order does not belong to this customer",
        )

    # 2. Check if a non-rejected refund already exists for this order
    existing_refund = (
        db.query(Refund)
        .filter(Refund.order_id == oid)
        .filter(Refund.status.in_(["completed", "succeeded", "pending"]))
        .first()
    )
    if existing_refund:
        if idempotency_key and existing_refund.idempotency_key == str(idempotency_key):
            return ToolResult(
                success=True,
                data={
                    "refund_id": existing_refund.id,
                    "order_id": oid,
                    "amount": float(existing_refund.amount),
                    "status": existing_refund.status,
                    "message": f"Idempotent replay: Refund already processed (ID: {existing_refund.id}).",
                },
            )
        return ToolResult(
            success=False,
            data={
                "refund_id": existing_refund.id,
                "order_id": oid,
                "amount": float(existing_refund.amount),
                "status": existing_refund.status,
            },
            error=f"Order {order_id} already has a refund processed (refund ID: {existing_refund.id}).",
        )

    # 3. Create the refund record
    refund = Refund(
        customer_id=cid,
        order_id=oid,
        amount=amount,
        reason=reason,
        status="pending",
        idempotency_key=str(idempotency_key) if idempotency_key else None,
        created_at=datetime.now(UTC),
    )
    db.add(refund)

    try:
        db.commit()
        db.refresh(refund)
    except Exception:
        # Atomic database race condition resolution
        db.rollback()
        # Query committed record
        conflict_refund = None
        if idempotency_key:
            conflict_refund = (
                db.query(Refund).filter(Refund.idempotency_key == str(idempotency_key)).first()
            )
        if not conflict_refund:
            conflict_refund = (
                db.query(Refund)
                .filter(Refund.order_id == oid)
                .filter(Refund.status.in_(["completed", "succeeded", "pending"]))
                .first()
            )

        if conflict_refund:
            return ToolResult(
                success=True,
                data={
                    "refund_id": conflict_refund.id,
                    "order_id": conflict_refund.order_id,
                    "amount": float(conflict_refund.amount),
                    "status": conflict_refund.status,
                    "message": "Atomic database conflict resolved: prior refund committed.",
                },
            )
        raise

    return ToolResult(
        success=True,
        data={
            "refund_id": refund.id,
            "order_id": oid,
            "amount": float(refund.amount),
            "status": refund.status,
            "message": f"Refund of Rs {amount:,.2f} initiated. ETA: 5-7 business days.",
        },
    )


def cancel_order(db: Session, customer_id: str | int, order_id: str | int) -> ToolResult:
    """
    Cancel a pending order (only if not yet shipped).
    """
    oid = str(order_id)
    cid = str(customer_id)
    order = db.get(Order, oid)
    if not order:
        return ToolResult(success=False, data={}, error=f"Order {order_id} not found")

    if str(order.customer_id) != cid:
        return ToolResult(success=False, data={}, error="Order does not belong to this customer")

    if order.status == "shipped":
        return ToolResult(
            success=False,
            data={},
            error="Cannot cancel order that has already been shipped",
        )

    if order.status == "cancelled":
        return ToolResult(success=False, data={}, error="Order is already cancelled")

    old_status = order.status
    order.status = "cancelled"
    db.commit()

    return ToolResult(
        success=True,
        data={
            "order_id": oid,
            "previous_status": old_status,
            "new_status": "cancelled",
            "message": f"Order {order_id} successfully cancelled. Refund will be processed in 5-7 days.",
        },
    )


def check_inventory(db: Session, product_id: str | int) -> ToolResult:
    """Return current inventory level for a product."""
    pid = str(product_id)
    prod = db.get(Product, pid)
    if not prod:
        return ToolResult(
            success=False, data={}, error=f"Product {product_id} not found in inventory"
        )

    return ToolResult(
        success=True,
        data={
            "product_id": prod.id,
            "sku": prod.sku,
            "title": prod.title,
            "quantity": prod.inventory_count,
        },
    )
