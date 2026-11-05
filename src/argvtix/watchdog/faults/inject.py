"""
Fault Injection Module
Intentionally plants controlled data anomalies to test Watchdog detection accuracy.
Supports 8 Data Faults + 4 Integration Faults:

Data Faults:
1. duplicate_refund: multiple refunds issued for same order
2. total_mismatch: total_amount != sum(items) + tax
3. excess_refund: refund amount > payment amount
4. inventory_mismatch: inventory deduction logs missing
5. orphan_payment: payment record referencing a nonexistent order
6. negative_inventory: product inventory drops below 0
7. status_drift: order marked delivered while payment failed
8. ghost_order_item: order item attached to nonexistent product ID

Integration Faults (External Systems):
1. crm_amount_mismatch: CRM invoice amount differs from DB total
2. erp_status_mismatch: ERP status conflicts with DB status
3. gateway_desync: external payment gateway chargeback/refund unrecorded
4. warehouse_lag: order fulfilled but no tracking / 3PL dispatch lag
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from argvtix.db.models import Customer, InventoryLog, Order, OrderItem, Payment, Product, Refund
from argvtix.db.session import SessionLocal

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ============================================================================
# 8 Data Fault Injectors
# ============================================================================


def inject_duplicate_refunds(db: Session, count: int = 5) -> list[str]:
    """Plant duplicate refund records for existing orders."""
    candidate_orders = db.query(Order).join(Payment).all()
    if not candidate_orders:
        return []

    selected = random.sample(candidate_orders, k=min(count, len(candidate_orders)))
    injected_orders: list[str] = []

    for order in selected:
        pmt = order.payments[0] if order.payments else None
        for _ in range(2):
            dup = Refund(
                order_id=order.id,
                payment_id=pmt.id if pmt else None,
                customer_id=order.customer_id,
                amount=round(order.total_amount * 0.5, 2),
                reason="Fault Injection: Duplicate refund simulation",
                status="completed",
                processed_by="ai_agent",
                created_at=datetime.now(UTC) - timedelta(hours=random.randint(1, 12)),
            )
            db.add(dup)
        injected_orders.append(order.id)

    db.commit()
    return injected_orders


def inject_order_total_mismatches(db: Session, count: int = 5) -> list[str]:
    """Corrupt total_amount on orders so total != sum(items) + tax."""
    orders = db.query(Order).filter(Order.status == "completed").all()
    if not orders:
        orders = db.query(Order).all()
    if not orders:
        return []

    selected = random.sample(orders, k=min(count, len(orders)))
    injected_orders: list[str] = []

    for order in selected:
        corruption = random.choice([-250.0, 350.0, 500.0])
        order.total_amount = max(10.0, round(order.total_amount + corruption, 2))
        injected_orders.append(order.id)

    db.commit()
    return injected_orders


def inject_refund_exceeds_payment(db: Session, count: int = 5) -> list[str]:
    """Plant refund records where refund amount is 2x payment amount."""
    orders = db.query(Order).join(Payment).all()
    if not orders:
        return []

    selected = random.sample(orders, k=min(count, len(orders)))
    injected_orders: list[str] = []

    for order in selected:
        pmt = order.payments[0]
        excessive_refund = Refund(
            order_id=order.id,
            payment_id=pmt.id,
            customer_id=order.customer_id,
            amount=round(pmt.amount * 2.0, 2),
            reason="Fault Injection: Excess refund simulation",
            status="completed",
            processed_by="ai_agent",
            created_at=datetime.now(UTC),
        )
        db.add(excessive_refund)
        injected_orders.append(order.id)

    db.commit()
    return injected_orders


def inject_inventory_discrepancies(db: Session, count: int = 5) -> list[str]:
    """Remove inventory logs for completed orders to create discrepancies."""
    orders = db.query(Order).filter(Order.status == "completed").all()
    if not orders:
        return []

    selected = random.sample(orders, k=min(count, len(orders)))
    injected_orders: list[str] = []

    for order in selected:
        db.query(InventoryLog).filter(InventoryLog.order_id == order.id).delete()
        injected_orders.append(order.id)

    db.commit()
    return injected_orders


def inject_orphan_payments(db: Session, count: int = 5) -> list[str]:
    """Plant orphan payments that reference nonexistent orders."""
    injected_ids: list[str] = []
    cust = db.query(Customer).first()
    cust_id = cust.id if cust else "cust_orphan_fallback"
    for _ in range(count):
        pay_id = f"pay_orphan_{uuid.uuid4().hex[:8]}"
        orphan_order_id = f"ord_nonexistent_{uuid.uuid4().hex[:8]}"
        pmt = Payment(
            id=pay_id,
            order_id=orphan_order_id,
            customer_id=cust_id,
            amount=round(random.uniform(500.0, 5000.0), 2),
            status="succeeded",
        )
        db.add(pmt)
        injected_ids.append(pay_id)
    db.commit()
    return injected_ids


def inject_negative_inventory(db: Session, count: int = 5) -> list[str]:
    """Force product inventory_count to negative values without backorder allowance."""
    products = db.query(Product).all()
    if not products:
        return []
    selected = random.sample(products, k=min(count, len(products)))
    injected_skus: list[str] = []
    for prod in selected:
        prod.inventory_count = -random.randint(5, 50)
        injected_skus.append(prod.sku or prod.id)
    db.commit()
    return injected_skus


def inject_status_drift(db: Session, count: int = 5) -> list[str]:
    """Set order status to 'delivered' while associated payment is 'failed'."""
    orders = db.query(Order).join(Payment).all()
    if not orders:
        return []
    selected = random.sample(orders, k=min(count, len(orders)))
    injected_orders: list[str] = []
    for order in selected:
        order.status = "delivered"
        for p in order.payments:
            p.status = "failed"
        injected_orders.append(order.id)
    db.commit()
    return injected_orders


def inject_ghost_order_items(db: Session, count: int = 5) -> list[str]:
    """Inject order items attached to non-existent product IDs."""
    orders = db.query(Order).all()
    if not orders:
        return []
    selected = random.sample(orders, k=min(count, len(orders)))
    injected_items: list[str] = []
    for order in selected:
        ghost_item = OrderItem(
            id=f"item_ghost_{uuid.uuid4().hex[:8]}",
            order_id=order.id,
            product_id=f"prod_nonexistent_{uuid.uuid4().hex[:8]}",
            quantity=1,
            unit_price=999.0,
            line_total=999.0,
        )
        db.add(ghost_item)
        injected_items.append(ghost_item.id)
    db.commit()
    return injected_items


# ============================================================================
# 4 Integration Fault Generators (External System Desync)
# ============================================================================


def generate_crm_amount_mismatch_faults(
    orders: list[Order], corruption_delta: float = 500.0
) -> list[dict[str, Any]]:
    """Simulate CRM invoice amount mismatch against local order total."""
    faults: list[dict[str, Any]] = []
    for o in orders:
        crm_amount = round(o.total_amount + corruption_delta, 2)
        faults.append(
            {
                "order_id": o.id,
                "internal_total": o.total_amount,
                "crm_invoice_amount": crm_amount,
                "discrepancy": round(abs(crm_amount - o.total_amount), 2),
                "failure_type": "DISCREPANCY_TOTAL_AMOUNT",
            }
        )
    return faults


def generate_erp_status_mismatch_faults(orders: list[Order]) -> list[dict[str, Any]]:
    """Simulate ERP system status desync (e.g. ERP cancelled vs DB delivered)."""
    faults: list[dict[str, Any]] = []
    for o in orders:
        erp_status = "cancelled" if o.status == "delivered" else "delivered"
        faults.append(
            {
                "order_id": o.id,
                "db_status": o.status,
                "erp_status": erp_status,
                "failure_type": "STATUS_DESYNC",
            }
        )
    return faults


def generate_payment_gateway_desync_faults(payments: list[Payment]) -> list[dict[str, Any]]:
    """Simulate payment gateway desynchronization (external chargeback/refund not in DB)."""
    faults: list[dict[str, Any]] = []
    for p in payments:
        faults.append(
            {
                "payment_id": p.id,
                "order_id": p.order_id,
                "db_status": p.status,
                "gateway_status": "refunded_chargeback",
                "failure_type": "GATEWAY_DESYNC",
            }
        )
    return faults


def generate_warehouse_shipment_lag_faults(orders: list[Order]) -> list[dict[str, Any]]:
    """Simulate 3PL warehouse logistics sync failure: order fulfilled but no tracking."""
    faults: list[dict[str, Any]] = []
    for o in orders:
        faults.append(
            {
                "order_id": o.id,
                "db_fulfillment_status": "fulfilled",
                "logistics_status": "unmanifested_lag",
                "carrier_tracking": None,
                "failure_type": "WAREHOUSE_SHIPMENT_LAG",
            }
        )
    return faults


def main() -> None:
    parser = argparse.ArgumentParser(description="ARGVTIX Fault Injector")
    parser.add_argument(
        "--type",
        choices=[
            "duplicate_refund",
            "total_mismatch",
            "excess_refund",
            "inventory_mismatch",
            "orphan_payment",
            "negative_inventory",
            "status_drift",
            "ghost_order_item",
            "all",
        ],
        default="all",
        help="Type of fault to inject",
    )
    parser.add_argument("--count", type=int, default=5, help="Number of faults per type")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print(f"⚡ Injecting fault type '{args.type}' (count={args.count})...")
        results: dict[str, int] = {}

        if args.type in ["duplicate_refund", "all"]:
            dups = inject_duplicate_refunds(db, count=args.count)
            results["duplicate_refunds"] = len(dups)

        if args.type in ["total_mismatch", "all"]:
            totals = inject_order_total_mismatches(db, count=args.count)
            results["total_mismatches"] = len(totals)

        if args.type in ["excess_refund", "all"]:
            excess = inject_refund_exceeds_payment(db, count=args.count)
            results["excess_refunds"] = len(excess)

        if args.type in ["inventory_mismatch", "all"]:
            inv = inject_inventory_discrepancies(db, count=args.count)
            results["inventory_discrepancies"] = len(inv)

        if args.type in ["orphan_payment", "all"]:
            orph = inject_orphan_payments(db, count=args.count)
            results["orphan_payments"] = len(orph)

        if args.type in ["negative_inventory", "all"]:
            negs = inject_negative_inventory(db, count=args.count)
            results["negative_inventory"] = len(negs)

        if args.type in ["status_drift", "all"]:
            drift = inject_status_drift(db, count=args.count)
            results["status_drift"] = len(drift)

        if args.type in ["ghost_order_item", "all"]:
            ghost = inject_ghost_order_items(db, count=args.count)
            results["ghost_order_items"] = len(ghost)

        print("✅ Fault injection complete:")
        for fault_type, n in results.items():
            print(f"   • {fault_type}: {n} injected")
    finally:
        db.close()


if __name__ == "__main__":
    main()
