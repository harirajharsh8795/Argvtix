"""
Test Suite for Action Guard Engine
Tests pre-action policy evaluation:
- Non-existent order blocked
- Customer mismatch blocked
- Duplicate refund blocked
- Excess refund blocked
- High-value transaction (>₹10,000) routed to ASK_HUMAN
- Normal valid transaction ALLOWed
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from earp.db.models import Base, Customer, Order, Payment, Refund
from earp.guard.engine import ActionGuard, GuardCheckRequest
from earp.trace.schemas import GuardDecision, Severity


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite database session for isolated testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # Seed baseline customer, order, payment
    cust = Customer(
        id="cust_101", name="Rahul Sharma", email="rahul@example.com", phone="+919876543210"
    )
    session.add(cust)

    order = Order(
        id="ord_201",
        customer_id="cust_101",
        status="completed",
        subtotal=4000.0,
        tax=720.0,
        total_amount=4720.0,
    )
    session.add(order)

    payment = Payment(
        id="pmt_301",
        order_id="ord_201",
        customer_id="cust_101",
        amount=4720.0,
        status="succeeded",
    )
    session.add(payment)

    session.commit()
    yield session
    session.close()


def test_guard_blocks_nonexistent_order(db_session: Session) -> None:
    guard = ActionGuard()
    req = GuardCheckRequest(
        customer_id="cust_101",
        order_id="ord_nonexistent",
        amount=500.0,
    )
    res = guard.evaluate(req, db_session)
    assert res.decision == GuardDecision.BLOCK
    assert "does not exist" in res.reason


def test_guard_blocks_customer_mismatch(db_session: Session) -> None:
    guard = ActionGuard()
    req = GuardCheckRequest(
        customer_id="cust_imposter",
        order_id="ord_201",
        amount=500.0,
    )
    res = guard.evaluate(req, db_session)
    assert res.decision == GuardDecision.BLOCK
    assert "Customer ID mismatch" in res.reason
    assert res.risk_level == Severity.CRITICAL


def test_guard_allows_valid_refund(db_session: Session) -> None:
    guard = ActionGuard()
    req = GuardCheckRequest(
        customer_id="cust_101",
        order_id="ord_201",
        amount=2000.0,
    )
    res = guard.evaluate(req, db_session)
    assert res.decision == GuardDecision.ALLOW
    assert res.requires_human_approval is False


def test_guard_blocks_duplicate_refund(db_session: Session) -> None:
    guard = ActionGuard()
    # Plant prior refund
    prior_refund = Refund(
        order_id="ord_201",
        customer_id="cust_101",
        amount=2000.0,
        status="completed",
    )
    db_session.add(prior_refund)
    db_session.commit()

    req = GuardCheckRequest(
        customer_id="cust_101",
        order_id="ord_201",
        amount=2000.0,
    )
    res = guard.evaluate(req, db_session)
    assert res.decision == GuardDecision.BLOCK
    assert "Duplicate refund prevented" in res.reason


def test_guard_blocks_excess_refund(db_session: Session) -> None:
    guard = ActionGuard()
    req = GuardCheckRequest(
        customer_id="cust_101",
        order_id="ord_201",
        amount=9000.0,  # Paid was 4720
    )
    res = guard.evaluate(req, db_session)
    assert res.decision == GuardDecision.BLOCK
    assert "exceeds total payments" in res.reason


def test_guard_routes_large_refund_to_human_approval(db_session: Session) -> None:
    guard = ActionGuard()
    # Create expensive order
    expensive_order = Order(
        id="ord_expensive",
        customer_id="cust_101",
        status="completed",
        subtotal=15000.0,
        tax=2700.0,
        total_amount=17700.0,
    )
    db_session.add(expensive_order)
    db_session.add(
        Payment(
            id="pmt_expensive",
            order_id="ord_expensive",
            customer_id="cust_101",
            amount=17700.0,
            status="succeeded",
        )
    )
    db_session.commit()

    req = GuardCheckRequest(
        customer_id="cust_101",
        order_id="ord_expensive",
        amount=12000.0,  # > ₹10,000 threshold
    )
    res = guard.evaluate(req, db_session)
    assert res.decision == GuardDecision.ASK_HUMAN
    assert res.requires_human_approval is True
    assert "Queued for human approval" in res.reason
