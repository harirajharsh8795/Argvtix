"""
Test Suite for Watchdog Rules & Engine
Tests detection of:
- Rule 1: duplicate refunds
- Rule 2: order total mismatch
- Rule 3: refund exceeds payment
- Rule 4: inventory discrepancies
- Engine scanning and finding persistence
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from earp.db.models import (
    Base,
    Customer,
    InventoryLog,
    Order,
    OrderItem,
    Payment,
    Product,
    WatchdogFindingRecord,
)
from earp.watchdog.engine import WatchdogEngine
from earp.watchdog.faults.inject import (
    inject_duplicate_refunds,
    inject_inventory_discrepancies,
    inject_order_total_mismatches,
    inject_refund_exceeds_payment,
)
from earp.watchdog.rules.duplicate_refund import DuplicateRefundRule
from earp.watchdog.rules.inventory_discrepancy import InventoryDiscrepancyRule
from earp.watchdog.rules.order_total_mismatch import OrderTotalMismatchRule
from earp.watchdog.rules.refund_exceeds_payment import RefundExceedsPaymentRule


@pytest.fixture
def test_db() -> Session:
    """Isolated in-memory database with populated clean orders."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Product
    prod = Product(id="prod_1", sku="SKU-1", title="Headphones", price=1000.0, inventory_count=50)
    session.add(prod)

    # Customer
    cust = Customer(id="cust_1", name="Priya Singh", email="priya@example.com")
    session.add(cust)

    # Clean Order
    order = Order(
        id="order_clean",
        customer_id="cust_1",
        status="completed",
        subtotal=2000.0,
        tax=360.0,
        total_amount=2360.0,
    )
    session.add(order)

    # Order Items
    item = OrderItem(
        id="item_1",
        order_id="order_clean",
        product_id="prod_1",
        quantity=2,
        unit_price=1000.0,
        line_total=2000.0,
    )
    session.add(item)

    # Payment
    pmt = Payment(
        id="pmt_1",
        order_id="order_clean",
        customer_id="cust_1",
        amount=2360.0,
        status="succeeded",
    )
    session.add(pmt)

    # Inventory Log
    inv = InventoryLog(
        id="inv_1",
        product_id="prod_1",
        change_amount=-2,
        reason="order_placed",
        order_id="order_clean",
    )
    session.add(inv)

    session.commit()
    yield session
    session.close()


def test_clean_database_has_zero_findings(test_db: Session) -> None:
    engine = WatchdogEngine()
    report = engine.scan(test_db, persist=False)
    assert report["total_findings"] == 0


def test_rule_1_duplicate_refund_detected(test_db: Session) -> None:
    rule = DuplicateRefundRule()
    assert len(rule.scan(test_db)) == 0

    # Inject duplicate refund
    inject_duplicate_refunds(test_db, count=1)
    findings = rule.scan(test_db)
    assert len(findings) == 1
    assert findings[0].rule_name == "duplicate_refund"
    assert findings[0].entity_id == "order_clean"


def test_rule_2_order_total_mismatch_detected(test_db: Session) -> None:
    rule = OrderTotalMismatchRule()
    assert len(rule.scan(test_db)) == 0

    # Corrupt total amount
    inject_order_total_mismatches(test_db, count=1)
    findings = rule.scan(test_db)
    assert len(findings) == 1
    assert findings[0].rule_name == "order_total_mismatch"


def test_rule_3_refund_exceeds_payment_detected(test_db: Session) -> None:
    rule = RefundExceedsPaymentRule()
    assert len(rule.scan(test_db)) == 0

    # Inject excess refund
    inject_refund_exceeds_payment(test_db, count=1)
    findings = rule.scan(test_db)
    assert len(findings) == 1
    assert findings[0].rule_name == "refund_exceeds_payment"


def test_rule_4_inventory_discrepancy_detected(test_db: Session) -> None:
    rule = InventoryDiscrepancyRule()
    assert len(rule.scan(test_db)) == 0

    # Remove inventory logs
    inject_inventory_discrepancies(test_db, count=1)
    findings = rule.scan(test_db)
    assert len(findings) == 1
    assert findings[0].rule_name == "inventory_discrepancy"


def test_watchdog_engine_persists_findings(test_db: Session) -> None:
    # Inject 2 faults
    inject_duplicate_refunds(test_db, count=1)
    inject_order_total_mismatches(test_db, count=1)

    engine = WatchdogEngine()
    report = engine.scan(test_db, persist=True)
    assert report["total_findings"] >= 2

    # Verify persisted in database
    records = test_db.query(WatchdogFindingRecord).all()
    assert len(records) >= 2
    rule_names = {r.rule_name for r in records}
    assert "duplicate_refund" in rule_names
    assert "order_total_mismatch" in rule_names
