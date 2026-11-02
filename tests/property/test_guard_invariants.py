"""
Hypothesis Property-Based Invariant Tests for ActionGuard & ToolGateway.

Proves mathematical and security invariants over hundreds of randomized inputs:
- Invariant 1: If Guard returns BLOCK or ASK_HUMAN, ToolGateway.call() makes ZERO database writes.
- Invariant 2: Nonexistent orders are unconditionally BLOCKED.
- Invariant 3: Customer mismatch is unconditionally BLOCKED.
- Invariant 4: Excess refund (amount > payment) is unconditionally BLOCKED.
- Invariant 5: Valid refund below threshold is unconditionally ALLOWed.
- Invariant 6: High-value refund (>= ₹10,000) is unconditionally routed to ASK_HUMAN.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from argvtix.db.models import Base, Customer, Order, Payment, Refund
from argvtix.guard.engine import ActionGuard, GuardCheckRequest
from argvtix.guard.gateway import ToolGateway
from argvtix.trace.schemas import GuardDecision


def create_seeded_session() -> tuple[Session, str, str, float]:
    """Helper creating fresh in-memory DB with known baseline order."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()

    cust_id = "cust_prop_101"
    order_id = "ord_prop_201"
    order_total = 5000.0

    cust = Customer(id=cust_id, name="Priya Patel", email="priya@example.com")
    db.add(cust)

    order = Order(
        id=order_id,
        customer_id=cust_id,
        status="completed",
        subtotal=4500.0,
        tax=500.0,
        total_amount=order_total,
    )
    db.add(order)

    payment = Payment(
        id="pmt_prop_301",
        order_id=order_id,
        customer_id=cust_id,
        amount=order_total,
        status="succeeded",
    )
    db.add(payment)
    db.commit()

    return db, cust_id, order_id, order_total


class TestGuardInvariantsHypothesis:
    """Property test suite proving Guard invariants."""

    @settings(max_examples=50, deadline=None)
    @given(amount=st.floats(min_value=0.0, max_value=200000.0))
    def test_invariant_block_or_ask_human_means_zero_refund_writes(self, amount: float) -> None:
        """
        Invariant 1: For ALL inputs where Guard decides BLOCK or ASK_HUMAN,
        ToolGateway MUST NOT write any refund record to the database.
        """
        db, cust_id, order_id, max_paid = create_seeded_session()
        try:
            gateway = ToolGateway()
            initial_count = db.query(Refund).count()

            # Attempt refund
            res = gateway.call(
                "issue_refund",
                {"order_id": order_id, "customer_id": cust_id, "amount": amount},
                db=db,
            )

            if res.decision in (GuardDecision.BLOCK, GuardDecision.ASK_HUMAN):
                assert db.query(Refund).count() == initial_count
            elif res.decision == GuardDecision.ALLOW:
                assert db.query(Refund).count() == initial_count + 1
        finally:
            db.close()

    @settings(max_examples=50, deadline=None)
    @given(fake_order_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=30))
    def test_invariant_nonexistent_order_always_blocked(self, fake_order_id: str) -> None:
        """
        Invariant 2: Any order_id that does not exist in the database MUST be BLOCKED.
        """
        db, cust_id, order_id, _ = create_seeded_session()
        try:
            # Ensure fake_order_id does not collide with our seeded order
            if fake_order_id == order_id:
                return

            guard = ActionGuard()
            req = GuardCheckRequest(
                workflow_type="refund",
                tool_name="issue_refund",
                customer_id=cust_id,
                order_id=fake_order_id,
                amount=100.0,
            )
            res = guard.evaluate(req, db)
            assert res.decision == GuardDecision.BLOCK
            assert res.policy_rule_triggered == "verify_order_exists"
        finally:
            db.close()

    @settings(max_examples=50, deadline=None)
    @given(wrong_customer_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=30))
    def test_invariant_customer_mismatch_always_blocked(self, wrong_customer_id: str) -> None:
        """
        Invariant 3: Any customer attempting to act on someone else's order MUST be BLOCKED.
        """
        db, cust_id, order_id, _ = create_seeded_session()
        try:
            if wrong_customer_id == cust_id:
                return

            guard = ActionGuard()
            req = GuardCheckRequest(
                workflow_type="refund",
                tool_name="issue_refund",
                customer_id=wrong_customer_id,
                order_id=order_id,
                amount=100.0,
            )
            res = guard.evaluate(req, db)
            assert res.decision == GuardDecision.BLOCK
            assert res.policy_rule_triggered == "verify_customer_ownership"
        finally:
            db.close()

    @settings(max_examples=50, deadline=None)
    @given(excess_multiplier=st.floats(min_value=1.01, max_value=50.0))
    def test_invariant_excess_refund_always_blocked(self, excess_multiplier: float) -> None:
        """
        Invariant 4: Any refund amount strictly greater than total payment MUST be BLOCKED.
        """
        db, cust_id, order_id, total_paid = create_seeded_session()
        try:
            excess_amount = total_paid * excess_multiplier
            guard = ActionGuard()
            req = GuardCheckRequest(
                workflow_type="refund",
                tool_name="issue_refund",
                customer_id=cust_id,
                order_id=order_id,
                amount=excess_amount,
            )
            res = guard.evaluate(req, db)
            assert res.decision == GuardDecision.BLOCK
            assert res.policy_rule_triggered == "cap_refund_at_payment"
        finally:
            db.close()

    @settings(max_examples=50, deadline=None)
    @given(amount=st.floats(min_value=1.0, max_value=4999.0))
    def test_invariant_valid_refund_under_threshold_is_allowed(self, amount: float) -> None:
        """
        Invariant 5: Valid order, matching customer, amount <= total_paid, amount < 10,000 -> ALLOW.
        """
        db, cust_id, order_id, total_paid = create_seeded_session()
        try:
            guard = ActionGuard()
            req = GuardCheckRequest(
                workflow_type="refund",
                tool_name="issue_refund",
                customer_id=cust_id,
                order_id=order_id,
                amount=amount,
            )
            res = guard.evaluate(req, db)
            assert res.decision == GuardDecision.ALLOW
        finally:
            db.close()

    @settings(max_examples=50, deadline=None)
    @given(amount=st.floats(min_value=10000.0, max_value=50000.0))
    def test_invariant_high_value_refund_routes_to_human(self, amount: float) -> None:
        """
        Invariant 6: When payment is high enough (e.g. ₹60,000) and amount >= ₹10,000,
        it MUST route to ASK_HUMAN.
        """
        # Create DB with high value payment
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        session_factory = sessionmaker(bind=engine)
        db = session_factory()

        cust_id = "cust_high_1"
        order_id = "ord_high_1"

        cust = Customer(id=cust_id, name="Vikram", email="vikram@example.com")
        db.add(cust)
        order = Order(id=order_id, customer_id=cust_id, status="completed", total_amount=100000.0)
        db.add(order)
        payment = Payment(id="pmt_high_1", order_id=order_id, customer_id=cust_id, amount=100000.0, status="succeeded")
        db.add(payment)
        db.commit()

        try:
            guard = ActionGuard()
            req = GuardCheckRequest(
                workflow_type="refund",
                tool_name="issue_refund",
                customer_id=cust_id,
                order_id=order_id,
                amount=amount,
            )
            res = guard.evaluate(req, db)
            assert res.decision == GuardDecision.ASK_HUMAN
            assert res.requires_human_approval is True
        finally:
            db.close()
