"""
Test Suite for ToolGateway MCP Proxy.

Validates:
1. Read tools execute without Guard blocking.
2. Valid write tool executions return ALLOW and commit DB updates.
3. Policy-violating requests return BLOCK with ZERO DB writes.
4. High-value requests return ASK_HUMAN with ZERO business DB writes and enqueue into approval queue.
5. Idempotency key caching prevents duplicate tool execution.
6. Custom tool registration and execution.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from argvtix.db.models import ApprovalQueueRecord, Base, Customer, Order, Payment, Refund
from argvtix.guard.gateway import ToolGateway
from argvtix.trace.schemas import GuardDecision


@pytest.fixture
def db() -> Session:
    """In-memory SQLite session with test fixtures."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    cust = Customer(id="cust_gw_1", name="Aarav Gupta", email="aarav@example.com")
    session.add(cust)

    order = Order(
        id="ord_gw_1",
        customer_id="cust_gw_1",
        status="completed",
        subtotal=2000.0,
        tax=360.0,
        total_amount=2360.0,
    )
    session.add(order)

    payment = Payment(
        id="pmt_gw_1",
        order_id="ord_gw_1",
        customer_id="cust_gw_1",
        amount=2360.0,
        status="succeeded",
    )
    session.add(payment)

    # Order with sufficient total for high-value tests (>₹10,000)
    order_high = Order(
        id="ord_gw_high",
        customer_id="cust_gw_1",
        status="completed",
        subtotal=20000.0,
        tax=3600.0,
        total_amount=23600.0,
    )
    session.add(order_high)
    payment_high = Payment(
        id="pmt_gw_high",
        order_id="ord_gw_high",
        customer_id="cust_gw_1",
        amount=23600.0,
        status="succeeded",
    )
    session.add(payment_high)

    session.commit()

    yield session
    session.close()


class TestToolGateway:
    """Test suite for ToolGateway enforcement proxy."""

    def test_read_tool_execution(self, db: Session) -> None:
        gateway = ToolGateway()
        res = gateway.call("get_order", {"order_id": "ord_gw_1"}, db=db)
        assert res.decision == GuardDecision.ALLOW
        assert res.success is True
        assert res.data["order_id"] == "ord_gw_1"
        assert res.data["customer_id"] == "cust_gw_1"

    def test_valid_refund_allowed_and_executed(self, db: Session) -> None:
        gateway = ToolGateway()
        initial_refunds = db.query(Refund).count()

        res = gateway.call(
            "issue_refund",
            {"order_id": "ord_gw_1", "customer_id": "cust_gw_1", "amount": 500.0},
            db=db,
        )

        assert res.decision == GuardDecision.ALLOW
        assert res.success is True
        assert res.status == "completed"
        # Database write actually occurred
        assert db.query(Refund).count() == initial_refunds + 1
        new_refund = db.query(Refund).filter_by(order_id="ord_gw_1").first()
        assert new_refund is not None
        assert new_refund.amount == 500.0

    def test_block_nonexistent_order_makes_zero_db_writes(self, db: Session) -> None:
        gateway = ToolGateway()
        initial_refunds = db.query(Refund).count()

        res = gateway.call(
            "issue_refund",
            {"order_id": "ord_fake_999", "customer_id": "cust_gw_1", "amount": 500.0},
            db=db,
        )

        assert res.decision == GuardDecision.BLOCK
        assert res.success is False
        assert res.status == "blocked"
        assert "does not exist" in str(res.error)
        # ZERO database writes
        assert db.query(Refund).count() == initial_refunds

    def test_block_customer_mismatch_makes_zero_db_writes(self, db: Session) -> None:
        gateway = ToolGateway()
        initial_refunds = db.query(Refund).count()

        res = gateway.call(
            "issue_refund",
            {"order_id": "ord_gw_1", "customer_id": "cust_wrong_99", "amount": 500.0},
            db=db,
        )

        assert res.decision == GuardDecision.BLOCK
        assert res.success is False
        assert "Customer ID mismatch" in str(res.error)
        assert db.query(Refund).count() == initial_refunds

    def test_ask_human_routes_to_approval_queue_without_business_write(self, db: Session) -> None:
        gateway = ToolGateway()
        initial_refunds = db.query(Refund).count()
        initial_approvals = db.query(ApprovalQueueRecord).count()

        # ₹15,000 exceeds ₹10,000 threshold, but is within ₹23,600 payment
        res = gateway.call(
            "issue_refund",
            {"order_id": "ord_gw_high", "customer_id": "cust_gw_1", "amount": 15000.0},
            db=db,
        )

        assert res.decision == GuardDecision.ASK_HUMAN
        assert res.success is False
        assert res.status == "pending_approval"
        assert res.approval_id is not None

        # ZERO business table writes
        assert db.query(Refund).count() == initial_refunds

        # Enqueued in approval queue table
        assert db.query(ApprovalQueueRecord).count() == initial_approvals + 1
        record = db.query(ApprovalQueueRecord).filter_by(id=res.approval_id).first()
        assert record is not None
        assert record.amount == 15000.0
        assert record.status == "pending"

    def test_idempotency_prevents_duplicate_tool_execution(self, db: Session) -> None:
        gateway = ToolGateway()
        initial_refunds = db.query(Refund).count()
        idem_key = "idemp_unique_key_101"

        res1 = gateway.call(
            "issue_refund",
            {"order_id": "ord_gw_1", "customer_id": "cust_gw_1", "amount": 300.0},
            db=db,
            idempotency_key=idem_key,
        )
        assert res1.decision == GuardDecision.ALLOW
        assert db.query(Refund).count() == initial_refunds + 1

        # Second call with the same idempotency key
        res2 = gateway.call(
            "issue_refund",
            {"order_id": "ord_gw_1", "customer_id": "cust_gw_1", "amount": 300.0},
            db=db,
            idempotency_key=idem_key,
        )
        assert res2.decision == GuardDecision.ALLOW
        # No second row inserted!
        assert db.query(Refund).count() == initial_refunds + 1

    def test_unregistered_tool_returns_error(self, db: Session) -> None:
        gateway = ToolGateway()
        res = gateway.call("non_existent_tool", {}, db=db)
        assert res.decision == GuardDecision.BLOCK
        assert res.status == "error"
        assert "not registered" in str(res.error)

    def test_custom_tool_registration(self, db: Session) -> None:
        gateway = ToolGateway()
        called = {"count": 0}

        def custom_handler(item: str) -> dict:
            called["count"] += 1
            return {"echo": item}

        gateway.register_tool("echo_tool", custom_handler, is_write=False)
        res = gateway.call("echo_tool", {"item": "hello_argvtix"}, db=db)
        assert res.decision == GuardDecision.ALLOW
        assert res.data["echo"] == "hello_argvtix"
        assert called["count"] == 1
