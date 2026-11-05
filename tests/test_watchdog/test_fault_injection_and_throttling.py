"""
Tests for Watchdog 8 Data Faults + 4 Integration Faults, Alert Deduplication, Throttling, and Delivery.
Verifies Audit Weakness 14.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, Customer, InventoryLog, Order, OrderItem, Payment, Product
from argvtix.watchdog.alerts import AlertChannel, AlertDispatcher, AlertPayload, AlertSeverity
from argvtix.watchdog.faults.inject import (
    generate_crm_amount_mismatch_faults,
    generate_erp_status_mismatch_faults,
    generate_payment_gateway_desync_faults,
    generate_warehouse_shipment_lag_faults,
    inject_duplicate_refunds,
    inject_ghost_order_items,
    inject_inventory_discrepancies,
    inject_negative_inventory,
    inject_order_total_mismatches,
    inject_orphan_payments,
    inject_refund_exceeds_payment,
    inject_status_drift,
)
from argvtix.watchdog.reconcile.engine import ReconciliationEngine
from argvtix.watchdog.reconcile.schemas import ExternalEntityState
from argvtix.watchdog.rules.duplicate_refund import DuplicateRefundRule
from argvtix.watchdog.rules.inventory_discrepancy import InventoryDiscrepancyRule
from argvtix.watchdog.rules.order_total_mismatch import OrderTotalMismatchRule
from argvtix.watchdog.rules.orphan_payment import OrphanPaymentRule
from argvtix.watchdog.rules.refund_exceeds_payment import RefundExceedsPaymentRule


@pytest.fixture
def fault_db() -> Session:
    """Isolated SQLite database seeded with clean test data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    cust = Customer(id="cust_f1", name="Aarav Sharma", email="aarav@example.com")
    prod = Product(
        id="prod_f1", sku="SKU-F1", title="Mechanical Keyboard", price=2500.0, inventory_count=20
    )
    order = Order(
        id="ord_f1",
        customer_id="cust_f1",
        status="completed",
        subtotal=2500.0,
        tax=450.0,
        total_amount=2950.0,
    )
    item = OrderItem(
        id="item_f1",
        order_id="ord_f1",
        product_id="prod_f1",
        quantity=1,
        unit_price=2500.0,
        line_total=2500.0,
    )
    pmt = Payment(
        id="pay_f1",
        order_id="ord_f1",
        customer_id="cust_f1",
        amount=2950.0,
        status="succeeded",
    )
    inv = InventoryLog(
        id="inv_f1",
        product_id="prod_f1",
        order_id="ord_f1",
        change_amount=-1,
        reason="order_placed",
    )

    session.add_all([cust, prod, order, item, pmt, inv])
    session.commit()

    yield session
    session.close()


# ============================================================================
# 8 Data Faults Verification
# ============================================================================


class TestEightDataFaults:
    def test_fault_1_duplicate_refund_injected_and_detected(self, fault_db: Session) -> None:
        injected = inject_duplicate_refunds(fault_db, count=1)
        assert len(injected) == 1
        rule = DuplicateRefundRule()
        findings = rule.scan(fault_db)
        assert len(findings) >= 1
        assert any(f.entity_id == "ord_f1" for f in findings)

    def test_fault_2_order_total_mismatch_injected_and_detected(self, fault_db: Session) -> None:
        injected = inject_order_total_mismatches(fault_db, count=1)
        assert len(injected) == 1
        rule = OrderTotalMismatchRule()
        findings = rule.scan(fault_db)
        assert len(findings) >= 1
        assert any(f.entity_id == "ord_f1" for f in findings)

    def test_fault_3_refund_exceeds_payment_injected_and_detected(self, fault_db: Session) -> None:
        injected = inject_refund_exceeds_payment(fault_db, count=1)
        assert len(injected) == 1
        rule = RefundExceedsPaymentRule()
        findings = rule.scan(fault_db)
        assert len(findings) >= 1
        assert any(f.entity_id == "ord_f1" for f in findings)

    def test_fault_4_inventory_discrepancy_injected_and_detected(self, fault_db: Session) -> None:
        injected = inject_inventory_discrepancies(fault_db, count=1)
        assert len(injected) == 1
        rule = InventoryDiscrepancyRule()
        findings = rule.scan(fault_db)
        assert len(findings) >= 1
        assert any(f.entity_id == "ord_f1" for f in findings)

    def test_fault_5_orphan_payment_injected_and_detected(self, fault_db: Session) -> None:
        injected = inject_orphan_payments(fault_db, count=2)
        assert len(injected) == 2
        rule = OrphanPaymentRule()
        findings = rule.scan(fault_db)
        assert len(findings) >= 2
        assert any(f.entity_id in injected for f in findings)

    def test_fault_6_negative_inventory_injected(self, fault_db: Session) -> None:
        injected = inject_negative_inventory(fault_db, count=1)
        assert len(injected) == 1
        prod = fault_db.query(Product).filter(Product.id == "prod_f1").first()
        assert prod is not None
        assert prod.inventory_count < 0

    def test_fault_7_status_drift_injected(self, fault_db: Session) -> None:
        injected = inject_status_drift(fault_db, count=1)
        assert len(injected) == 1
        order = fault_db.query(Order).filter(Order.id == "ord_f1").first()
        assert order is not None
        assert order.status == "delivered"
        assert order.payments[0].status == "failed"

    def test_fault_8_ghost_order_items_injected(self, fault_db: Session) -> None:
        injected = inject_ghost_order_items(fault_db, count=1)
        assert len(injected) == 1
        item = fault_db.query(OrderItem).filter(OrderItem.id == injected[0]).first()
        assert item is not None
        assert "prod_nonexistent" in item.product_id


# ============================================================================
# 4 Integration Faults Verification
# ============================================================================


class TestFourIntegrationFaults:
    def test_integration_fault_1_crm_amount_mismatch(self, fault_db: Session) -> None:
        orders = fault_db.query(Order).all()
        faults = generate_crm_amount_mismatch_faults(orders, corruption_delta=750.0)
        assert len(faults) == 1
        assert faults[0]["discrepancy"] == 750.0

        # Check reconciliation engine detects it
        engine = ReconciliationEngine(db=fault_db)
        external = [
            ExternalEntityState(
                order_id=orders[0].id,
                crm_invoice_amount=faults[0]["crm_invoice_amount"],
            )
        ]
        res = engine.run_reconciliation(external_states=external)
        assert res.total_discrepancies >= 1
        assert any(it.failure_type.value == "discrepancy_total_amount" for it in res.items)

    def test_integration_fault_2_erp_status_mismatch(self, fault_db: Session) -> None:
        orders = fault_db.query(Order).all()
        orders[0].status = "delivered"
        fault_db.commit()

        faults = generate_erp_status_mismatch_faults(orders)
        assert len(faults) == 1
        assert faults[0]["erp_status"] == "cancelled"

        engine = ReconciliationEngine(db=fault_db)
        external = [
            ExternalEntityState(
                order_id=orders[0].id,
                erp_order_status="cancelled",
            )
        ]
        res = engine.run_reconciliation(external_states=external)
        assert any(it.failure_type.value == "status_desync" for it in res.items)

    def test_integration_fault_3_gateway_desync(self, fault_db: Session) -> None:
        payments = fault_db.query(Payment).all()
        faults = generate_payment_gateway_desync_faults(payments)
        assert len(faults) == 1
        assert faults[0]["gateway_status"] == "refunded_chargeback"
        assert faults[0]["db_status"] == "succeeded"

    def test_integration_fault_4_warehouse_shipment_lag(self, fault_db: Session) -> None:
        orders = fault_db.query(Order).all()
        faults = generate_warehouse_shipment_lag_faults(orders)
        assert len(faults) == 1
        assert faults[0]["carrier_tracking"] is None
        assert faults[0]["logistics_status"] == "unmanifested_lag"


# ============================================================================
# Alert Deduplication and Throttling Verification
# ============================================================================


class TestAlertDeduplicationAndThrottling:
    def test_alert_deduplication_suppresses_repeat_alerts(self) -> None:
        dispatcher = AlertDispatcher(dedup_window_seconds=60.0)
        dispatcher.clear()

        alert = AlertPayload(
            title="Spike in Blocks",
            message="ActionGuard intercepted 12 attacks",
            severity=AlertSeverity.CRITICAL,
            source="guard",
            metadata={"entity_id": "ord_999"},
        )

        # First dispatch -> Accepted
        r1 = dispatcher.dispatch(alert, channels=[AlertChannel.IN_MEMORY])
        assert r1.get("suppressed") is not True
        assert r1.get("in_memory") is True
        assert dispatcher.total_dispatched == 1
        assert dispatcher.total_suppressed == 0

        # Second identical dispatch immediately -> Suppressed
        r2 = dispatcher.dispatch(alert, channels=[AlertChannel.IN_MEMORY])
        assert r2.get("suppressed") is True
        assert r2.get("in_memory") is False
        assert dispatcher.total_dispatched == 1
        assert dispatcher.total_suppressed == 1

        # Third dispatch with bypass_dedup=True -> Dispatched
        r3 = dispatcher.dispatch(alert, channels=[AlertChannel.IN_MEMORY], bypass_dedup=True)
        assert r3.get("suppressed") is not True
        assert r3.get("in_memory") is True
        assert dispatcher.total_dispatched == 2

    def test_alert_throttling_caps_burst_volume(self) -> None:
        dispatcher = AlertDispatcher(
            dedup_window_seconds=1.0,
            max_alerts_per_minute=5,
        )
        dispatcher.clear()

        # Dispatch 5 distinct alerts -> all succeed
        for i in range(5):
            alert = AlertPayload(
                title=f"Unique Alert {i}",
                message="Testing rate throttle",
                source="guard",
                metadata={"entity_id": f"entity_{i}"},
            )
            res = dispatcher.dispatch(alert, channels=[AlertChannel.IN_MEMORY])
            assert res.get("in_memory") is True
            assert res.get("throttled") is not True

        assert dispatcher.total_dispatched == 5
        assert dispatcher.total_throttled == 0

        # 6th distinct alert within same minute -> Throttled
        overflow_alert = AlertPayload(
            title="Unique Alert 6",
            message="Testing rate throttle overflow",
            source="guard",
            metadata={"entity_id": "entity_6"},
        )
        res_overflow = dispatcher.dispatch(overflow_alert, channels=[AlertChannel.IN_MEMORY])
        assert res_overflow.get("throttled") is True
        assert dispatcher.total_throttled == 1
