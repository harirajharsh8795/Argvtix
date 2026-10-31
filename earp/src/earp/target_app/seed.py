"""
Realistic Synthetic Data Seeder for ShopOps.
Generates customers, products, orders, payments, inventory logs, and support tickets.
Ensures valid referential integrity and realistic distributions.
"""

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta

from faker import Faker
from sqlalchemy.orm import Session

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from earp.db.models import (
    Customer,
    InventoryLog,
    Order,
    OrderItem,
    Payment,
    Product,
    Refund,
    SupportTicket,
)
from earp.db.session import SessionLocal, init_db

fake = Faker("en_IN")  # Realistic Indian names, cities, and context

SAMPLE_CATEGORIES = ["Electronics", "Apparel", "Home & Kitchen", "Books", "Personal Care"]
PRODUCT_CATALOG = [
    ("EL-001", "Wireless Noise Cancelling Earbuds", 2499.0, "Electronics"),
    ("EL-002", "Mechanical Keyboard RGB", 3999.0, "Electronics"),
    ("EL-003", "Fast Charging Power Bank 20000mAh", 1799.0, "Electronics"),
    ("EL-004", "Smartwatch Fitness Tracker", 3499.0, "Electronics"),
    ("AP-001", "Cotton Crewneck T-Shirt (Navy)", 699.0, "Apparel"),
    ("AP-002", "Slim Fit Denim Jeans", 1999.0, "Apparel"),
    ("AP-003", "Running Shoes Breathable", 2999.0, "Apparel"),
    ("HK-001", "Stainless Steel Insulated Water Bottle", 899.0, "Home & Kitchen"),
    ("HK-002", "Non-Stick Ceramic Fry Pan", 1499.0, "Home & Kitchen"),
    ("HK-003", "Aroma Oil Diffuser & Humidifier", 1299.0, "Home & Kitchen"),
    ("BK-001", "Designing Data-Intensive Applications", 1250.0, "Books"),
    ("BK-002", "Atomic Habits by James Clear", 599.0, "Books"),
    ("PC-001", "Organic Green Tea Face Wash 150ml", 399.0, "Personal Care"),
    ("PC-002", "Sunscreen SPF 50 Matte Gel", 499.0, "Personal Care"),
]


def seed_database(db: Session, order_count: int = 1000) -> dict[str, int]:
    """Populate database with synthetic data."""
    init_db()

    # 1. Create or retrieve Products
    products: list[Product] = []
    for sku, title, price, cat in PRODUCT_CATALOG:
        existing = db.query(Product).filter_by(sku=sku).first()
        if not existing:
            p = Product(
                sku=sku,
                title=title,
                price=price,
                inventory_count=random.randint(50, 500),
                category=cat,
            )
            db.add(p)
            products.append(p)
        else:
            products.append(existing)
    db.commit()

    # 2. Create Customers (~30% of order count)
    customer_count = max(50, order_count // 3)
    customers: list[Customer] = []
    tiers = ["standard", "silver", "gold", "platinum"]
    tier_weights = [0.65, 0.20, 0.10, 0.05]

    for _ in range(customer_count):
        cust = Customer(
            name=fake.name(),
            email=fake.unique.email(),
            phone=f"+91{random.randint(7000000000, 9999999999)}",
            tier=random.choices(tiers, weights=tier_weights)[0],
            created_at=datetime.now(UTC) - timedelta(days=random.randint(30, 365)),
        )
        db.add(cust)
        customers.append(cust)
    db.commit()

    # 3. Create Orders, OrderItems, Payments, Inventory Logs
    statuses = ["completed", "completed", "completed", "cancelled", "refunded"]
    payment_methods = ["upi", "credit_card", "netbanking", "cod"]
    payment_weights = [0.55, 0.25, 0.15, 0.05]

    order_records: list[Order] = []
    payment_records: list[Payment] = []
    refund_records: list[Refund] = []
    ticket_records: list[SupportTicket] = []

    for _ in range(order_count):
        cust = random.choice(customers)
        status = random.choice(statuses)
        order_date = datetime.now(UTC) - timedelta(days=random.randint(1, 90))

        order = Order(
            customer_id=cust.id,
            status=status,
            subtotal=0.0,
            tax=0.0,
            total_amount=0.0,
            created_at=order_date,
        )
        db.add(order)
        db.flush()  # Generate order.id

        # Add 1 to 4 items
        item_count = random.randint(1, 4)
        chosen_products = random.sample(products, k=min(item_count, len(products)))
        subtotal = 0.0

        for prod in chosen_products:
            qty = random.randint(1, 3)
            line_total = prod.price * qty
            subtotal += line_total

            item = OrderItem(
                order_id=order.id,
                product_id=prod.id,
                quantity=qty,
                unit_price=prod.price,
                line_total=line_total,
            )
            db.add(item)

            # Inventory deduction for completed/placed orders
            inv_log = InventoryLog(
                product_id=prod.id,
                change_amount=-qty,
                reason="order_placed",
                order_id=order.id,
                created_at=order_date,
            )
            db.add(inv_log)

        tax = round(subtotal * 0.18, 2)  # 18% GST
        total_amount = round(subtotal + tax, 2)

        order.subtotal = subtotal
        order.tax = tax
        order.total_amount = total_amount
        order_records.append(order)

        # Payment record
        payment = Payment(
            order_id=order.id,
            customer_id=cust.id,
            amount=total_amount,
            status="succeeded" if status != "failed" else "failed",
            method=random.choices(payment_methods, weights=payment_weights)[0],
            transaction_ref=f"TXN-{fake.unique.hexify(text='^^^^^^^^^^^^^^').upper()}",
            created_at=order_date + timedelta(minutes=random.randint(1, 10)),
        )
        db.add(payment)
        payment_records.append(payment)
        db.flush()

        # If refunded status, add clean single refund
        if status == "refunded":
            refund = Refund(
                order_id=order.id,
                payment_id=payment.id,
                customer_id=cust.id,
                amount=total_amount,
                reason="Customer requested return within 7-day window",
                status="completed",
                processed_by="system",
                created_at=order_date + timedelta(days=random.randint(1, 5)),
            )
            db.add(refund)
            refund_records.append(refund)

            # Restock inventory
            for prod in chosen_products:
                db.add(
                    InventoryLog(
                        product_id=prod.id,
                        change_amount=1,
                        reason="return_restock",
                        order_id=order.id,
                        created_at=refund.created_at,
                    )
                )

        # 10% chance of support ticket
        if random.random() < 0.10:
            ticket = SupportTicket(
                customer_id=cust.id,
                order_id=order.id,
                subject=f"Inquiry regarding order #{order.id[:8]}",
                issue_description=fake.paragraph(nb_sentences=2),
                status=random.choice(["open", "in_progress", "resolved"]),
                priority=random.choice(["low", "medium", "high"]),
                created_at=order_date + timedelta(hours=random.randint(1, 48)),
            )
            db.add(ticket)
            ticket_records.append(ticket)

    db.commit()

    return {
        "products": len(products),
        "customers": len(customers),
        "orders": len(order_records),
        "payments": len(payment_records),
        "refunds": len(refund_records),
        "tickets": len(ticket_records),
    }


def main() -> None:
    """CLI entry point for seed command."""
    parser = argparse.ArgumentParser(description="Seed ShopOps database with synthetic records")
    parser.add_argument(
        "--count", type=int, default=1000, help="Number of orders to generate (default: 1000)"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print(f"🌱 Seeding database with {args.count} orders...")
        stats = seed_database(db, order_count=args.count)
        print("✅ Seeding complete:")
        for entity, count in stats.items():
            print(f"   • {entity.capitalize()}: {count:,}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
