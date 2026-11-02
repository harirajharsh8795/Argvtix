"""
Fault Injection Module
Intentionally plants controlled data anomalies to test Watchdog detection accuracy.
Supports:
1. duplicate_refund
2. total_mismatch
3. excess_refund
4. inventory_mismatch
"""

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from argvtix.db.models import InventoryLog, Order, Payment, Refund
from argvtix.db.session import SessionLocal

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def inject_duplicate_refunds(db: Session, count: int = 5) -> list[str]:
    """Plant duplicate refund records for existing orders."""
    # Find orders that have payments
    candidate_orders = db.query(Order).join(Payment).all()
    if not candidate_orders:
        return []

    selected = random.sample(candidate_orders, k=min(count, len(candidate_orders)))
    injected_orders: list[str] = []

    for order in selected:
        pmt = order.payments[0] if order.payments else None
        # Add 2 duplicate refunds for this order
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
        # Intentionally alter recorded total by ₹150 - ₹500
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
            amount=round(pmt.amount * 2.0, 2),  # 200% of payment
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
        # Delete inventory deduction logs for this order
        db.query(InventoryLog).filter(InventoryLog.order_id == order.id).delete()
        injected_orders.append(order.id)

    db.commit()
    return injected_orders


def main() -> None:
    parser = argparse.ArgumentParser(description="ARGVTIX Fault Injector")
    parser.add_argument(
        "--type",
        choices=[
            "duplicate_refund",
            "total_mismatch",
            "excess_refund",
            "inventory_mismatch",
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

        print("✅ Fault injection complete:")
        for fault_type, n in results.items():
            print(f"   • {fault_type}: {n} injected")
    finally:
        db.close()


if __name__ == "__main__":
    main()
