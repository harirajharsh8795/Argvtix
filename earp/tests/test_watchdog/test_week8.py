"""
Test Suite for Week 8 / Sprint A4:
- Sliding Window Anomaly Detection (Z-Score + IQR)
- Cross-System Reconciliation Engine (4 failure modes)
- Multi-Channel Alerting Pipeline (In-memory, Slack/Email stubs)
- LLM Token Spend Guard (Daily & Monthly budget caps)
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from earp.db.models import Base, Customer, Order, OrderItem, Payment, Product
from earp.target_app.spend_guard import LLMSpendGuard
from earp.watchdog.alerts import (
    AlertChannel,
    AlertDispatcher,
    AlertPayload,
    AlertSeverity,
)
from earp.watchdog.anomaly import (
    AnomalyDetector,
    AnomalySeverity,
    MetricDataPoint,
)
from earp.watchdog.reconcile.engine import ReconciliationEngine
from earp.watchdog.reconcile.schemas import (
    ExternalEntityState,
    ReconciliationFailureType,
    ReconciliationResult,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Seed baseline customer, product, order, payment
    cust = Customer(id="cust_w8_1", name="Vikram Roy", email="vikram@example.com")
    prod = Product(id="prod_w8_1", sku="SKU-W8-1", title="Echo Dot", price=3499.0, inventory_count=10)
    order = Order(id="ord_w8_1", customer_id="cust_w8_1", status="delivered", total_amount=3499.0)
    item = OrderItem(id="item_w8_1", order_id="ord_w8_1", product_id="prod_w8_1", quantity=1, unit_price=3499.0, line_total=3499.0)
    payment = Payment(id="pay_w8_1", order_id="ord_w8_1", customer_id="cust_w8_1", amount=3499.0, status="succeeded")

    session.add_all([cust, prod, order, item, payment])
    session.commit()

    yield session
    session.close()


# ============================================================================
# Anomaly Detection Unit Tests
# ============================================================================


class TestAnomalyDetection:
    def test_compute_stats_and_quantiles(self):
        values = [10.0, 12.0, 11.0, 13.0, 12.0]
        mean, std = AnomalyDetector.compute_stats(values)
        assert mean == pytest.approx(11.6, 0.1)
        assert std > 0

        q1, med, q3 = AnomalyDetector.compute_quantiles(values)
        assert q1 <= med <= q3

    def test_normal_time_series_has_zero_anomalies(self):
        detector = AnomalyDetector(min_history_size=5)
        # Consistent baseline
        series = [
            MetricDataPoint(metric_name="refund_rate", value=2.0)
            for _ in range(10)
        ]
        report = detector.analyze_series(series)
        assert report.anomalies_detected == 0
        assert report.is_anomalous is False

    def test_seeded_10x_refund_spike_detected_as_anomaly(self):
        detector = AnomalyDetector(z_threshold=2.5, min_history_size=5)
        # 10 baseline values around 5.0, then sudden 10x spike to 55.0
        baseline = [4.8, 5.2, 5.0, 5.1, 4.9, 5.3, 5.0, 5.1]
        spike = 55.0  # 10x spike!

        points = [MetricDataPoint(metric_name="refund_count", value=v) for v in baseline]
        points.append(MetricDataPoint(metric_name="refund_count", value=spike))

        report = detector.analyze_series(points)
        assert report.anomalies_detected >= 1
        assert report.is_anomalous is True

        incident = report.incidents[0]
        assert incident.metric_name == "refund_count"
        assert incident.current_value == 55.0
        assert incident.severity in (AnomalySeverity.WARNING, AnomalySeverity.CRITICAL)
        assert "spike" in incident.reason.lower() or "outlier" in incident.reason.lower()

    def test_iqr_outlier_detection(self):
        detector = AnomalyDetector(iqr_multiplier=1.5, min_history_size=5)
        history = [10.0, 11.0, 12.0, 10.5, 11.5, 11.0]
        outlier_high = 40.0

        incident = detector.detect_iqr(history, outlier_high, metric_name="latency_p95")
        assert incident is not None
        assert incident.method == "iqr"
        assert incident.current_value == 40.0

    def test_scan_db_metrics(self, db):
        detector = AnomalyDetector()
        report = detector.scan_db_metrics(db)
        assert report.total_points_analyzed > 0
        assert isinstance(report.is_anomalous, bool)


# ============================================================================
# ERP / CRM Reconciliation Unit Tests
# ============================================================================


class TestReconciliationEngine:
    def test_clean_state_has_zero_discrepancies(self, db):
        engine = ReconciliationEngine(db=db)
        external = [
            ExternalEntityState(
                order_id="ord_w8_1",
                crm_invoice_amount=3499.0,
                erp_order_status="delivered",
            )
        ]
        result: ReconciliationResult = engine.run_reconciliation(external_states=external)
        assert result.total_discrepancies == 0
        assert result.is_synchronized is True

    def test_amount_discrepancy_detected(self, db):
        engine = ReconciliationEngine(db=db)
        # Order ord_w8_1 total in DB is 3499.0, external CRM says 4999.0
        external = [
            ExternalEntityState(
                order_id="ord_w8_1",
                crm_invoice_amount=4999.0,
            )
        ]
        result = engine.run_reconciliation(external_states=external)
        assert result.total_discrepancies == 1
        assert result.is_synchronized is False
        assert result.items[0].failure_type == ReconciliationFailureType.DISCREPANCY_TOTAL_AMOUNT
        assert result.items[0].actual_value == 3499.0
        assert result.items[0].expected_value == 4999.0

    def test_status_desync_detected(self, db):
        engine = ReconciliationEngine(db=db)
        # DB status is "delivered", but ERP says "cancelled"
        external = [
            ExternalEntityState(
                order_id="ord_w8_1",
                erp_order_status="cancelled",
            )
        ]
        result = engine.run_reconciliation(external_states=external)
        assert any(it.failure_type == ReconciliationFailureType.STATUS_DESYNC for it in result.items)

    def test_orphan_payment_detected(self, db):
        # Insert orphan payment with non-existent order_id
        orphan = Payment(
            id="pay_orphan_99",
            order_id="ord_nonexistent_99",
            customer_id="cust_w8_1",
            amount=500.0,
            status="succeeded",
        )
        db.add(orphan)
        db.commit()

        engine = ReconciliationEngine(db=db)
        result = engine.run_reconciliation()
        assert any(
            it.failure_type == ReconciliationFailureType.ORPHAN_PAYMENT and it.entity_id == "pay_orphan_99"
            for it in result.items
        )

    def test_missing_inventory_deduction_detected(self, db):
        # Set product inventory to negative
        prod = db.query(Product).filter(Product.id == "prod_w8_1").first()
        prod.inventory_count = -5
        db.commit()

        engine = ReconciliationEngine(db=db)
        result = engine.run_reconciliation()
        assert any(
            it.failure_type == ReconciliationFailureType.MISSING_INVENTORY_DEDUCTION
            for it in result.items
        )


# ============================================================================
# Multi-Channel Alert Dispatcher Unit Tests
# ============================================================================


class TestAlertDispatcher:
    def test_in_memory_queue_dispatch_and_retrieve(self):
        dispatcher = AlertDispatcher(max_in_memory=10)
        dispatcher.clear()

        alert = AlertPayload(
            title="Spike in Blocks",
            message="ActionGuard blocked 15 requests in 60s",
            severity=AlertSeverity.CRITICAL,
            source="guard",
        )
        status_map = dispatcher.dispatch(alert, channels=[AlertChannel.IN_MEMORY])
        assert status_map["in_memory"] is True

        recent = dispatcher.get_recent_alerts(limit=5)
        assert len(recent) == 1
        assert recent[0].title == "Spike in Blocks"
        assert recent[0].severity == AlertSeverity.CRITICAL

    def test_multi_channel_stub_execution(self):
        dispatcher = AlertDispatcher()
        alert = AlertPayload(
            title="Test Multi Channel",
            message="Checking Slack and Email stubs",
            severity=AlertSeverity.INFO,
        )
        status_map = dispatcher.dispatch(
            alert,
            channels=[AlertChannel.IN_MEMORY, AlertChannel.SLACK, AlertChannel.EMAIL],
        )
        assert status_map["in_memory"] is True
        assert status_map["slack"] is True
        assert status_map["email"] is True


# ============================================================================
# LLM Spend Guard Unit Tests
# ============================================================================


class TestLLMSpendGuard:
    def test_within_budget_spend_allowed(self):
        guard = LLMSpendGuard(daily_cap_usd=10.0, monthly_cap_usd=100.0)
        assert guard.check_and_record(0.05) is True
        summary = guard.get_summary()
        assert summary["daily_spend_usd"] == 0.05
        assert summary["blocked_calls"] == 0
        assert summary["is_capped"] is False

    def test_exceeding_daily_budget_is_blocked(self):
        guard = LLMSpendGuard(daily_cap_usd=1.0, monthly_cap_usd=50.0)
        assert guard.check_and_record(0.8) is True
        # Next call of $0.50 exceeds $1.0 cap -> MUST BE BLOCKED
        assert guard.check_and_record(0.5) is False

        summary = guard.get_summary()
        assert summary["blocked_calls"] == 1
        assert summary["is_capped"] is False  # current spend is 0.8, projected exceeded cap

    def test_spend_guard_reset(self):
        guard = LLMSpendGuard(daily_cap_usd=5.0)
        guard.check_and_record(2.0)
        guard.reset()
        summary = guard.get_summary()
        assert summary["daily_spend_usd"] == 0.0
        assert summary["total_calls"] == 0
