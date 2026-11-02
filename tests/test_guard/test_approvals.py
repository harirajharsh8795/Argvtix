"""
Test Suite for Human-in-the-Loop ApprovalQueue.

Validates:
1. Enqueueing pending approvals.
2. Listing pending approvals.
3. Approving an action triggers tool execution through ToolGateway.
4. Rejecting an action halts execution without DB write.
5. Edit-and-approve modifies parameters and executes with verified input.
6. State machine prevents re-deciding settled requests.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from argvtix.db.models import Base, Customer, Order, Payment, Refund
from argvtix.guard.approvals import ApprovalQueue
from argvtix.guard.gateway import ToolGateway
from argvtix.trace.schemas import ApprovalStatus


@pytest.fixture
def db() -> Session:
    """In-memory SQLite session with test fixtures."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    cust = Customer(id="cust_appr_1", name="Meera Nambiar", email="meera@example.com")
    session.add(cust)

    order = Order(
        id="ord_appr_1",
        customer_id="cust_appr_1",
        status="completed",
        subtotal=15000.0,
        tax=2700.0,
        total_amount=17700.0,
    )
    session.add(order)

    payment = Payment(
        id="pmt_appr_1",
        order_id="ord_appr_1",
        customer_id="cust_appr_1",
        amount=17700.0,
        status="succeeded",
    )
    session.add(payment)
    session.commit()

    yield session
    session.close()


class TestApprovalQueue:
    """Tests for human approval review workflows."""

    def test_enqueue_and_list_pending(self, db: Session) -> None:
        queue = ApprovalQueue()
        record = queue.enqueue(
            action_type="issue_refund",
            tool_name="issue_refund",
            entity_id="ord_appr_1",
            customer_id="cust_appr_1",
            amount=12000.0,
            payload={"order_id": "ord_appr_1", "customer_id": "cust_appr_1", "amount": 12000.0},
            guard_reason="High value > ₹10,000",
            db=db,
        )

        assert record.id is not None
        assert record.status == ApprovalStatus.PENDING.value

        pending = queue.list_pending(db)
        assert len(pending) >= 1
        assert any(p.id == record.id for p in pending)

    def test_approve_executes_tool_via_gateway(self, db: Session) -> None:
        queue = ApprovalQueue()
        gateway = ToolGateway(approval_queue=queue)

        record = queue.enqueue(
            action_type="issue_refund",
            tool_name="issue_refund",
            entity_id="ord_appr_1",
            customer_id="cust_appr_1",
            amount=11000.0,
            payload={"order_id": "ord_appr_1", "customer_id": "cust_appr_1", "amount": 11000.0},
            guard_reason="High value refund",
            db=db,
        )

        initial_refunds = db.query(Refund).count()

        # Human approves
        updated_record, res = queue.approve(
            approval_id=record.id,
            reviewer_id="lead_reviewer_42",
            notes="Customer VIP, refund authorized",
            db=db,
            gateway=gateway,
        )

        assert updated_record.status == ApprovalStatus.APPROVED.value
        assert updated_record.reviewer_id == "lead_reviewer_42"
        assert updated_record.decided_at is not None

        # Tool was executed and DB has refund
        assert db.query(Refund).count() == initial_refunds + 1
        new_refund = db.query(Refund).filter_by(order_id="ord_appr_1").first()
        assert new_refund.amount == 11000.0

    def test_reject_halts_execution_without_db_write(self, db: Session) -> None:
        queue = ApprovalQueue()
        record = queue.enqueue(
            action_type="issue_refund",
            tool_name="issue_refund",
            entity_id="ord_appr_1",
            customer_id="cust_appr_1",
            amount=15000.0,
            payload={"order_id": "ord_appr_1", "customer_id": "cust_appr_1", "amount": 15000.0},
            guard_reason="Exceeds threshold",
            db=db,
        )

        initial_refunds = db.query(Refund).count()

        # Human rejects
        updated_record = queue.reject(
            approval_id=record.id,
            reviewer_id="compliance_officer_9",
            reason="Exceeded policy return window",
            db=db,
        )

        assert updated_record.status == ApprovalStatus.REJECTED.value
        assert updated_record.reviewer_notes == "Exceeded policy return window"
        # Zero writes to Refund table
        assert db.query(Refund).count() == initial_refunds

    def test_edit_and_approve(self, db: Session) -> None:
        queue = ApprovalQueue()
        gateway = ToolGateway(approval_queue=queue)

        record = queue.enqueue(
            action_type="issue_refund",
            tool_name="issue_refund",
            entity_id="ord_appr_1",
            customer_id="cust_appr_1",
            amount=14000.0,
            payload={"order_id": "ord_appr_1", "customer_id": "cust_appr_1", "amount": 14000.0},
            guard_reason="Requested full refund",
            db=db,
        )

        # Reviewer negotiates partial 50% refund (₹7000)
        edited_payload = {
            "order_id": "ord_appr_1",
            "customer_id": "cust_appr_1",
            "amount": 7000.0,
            "reason": "approved_partial_settlement",
        }

        updated_record, res = queue.edit_and_approve(
            approval_id=record.id,
            edited_payload=edited_payload,
            reviewer_id="manager_suresh",
            notes="Authorized 50% goodwill refund",
            db=db,
            gateway=gateway,
        )

        assert updated_record.status == ApprovalStatus.EDITED.value
        assert json.loads(updated_record.edited_payload_json)["amount"] == 7000.0

        # Refund in DB is for the EDITED amount ₹7000
        refund = db.query(Refund).filter_by(order_id="ord_appr_1").first()
        assert refund is not None
        assert refund.amount == 7000.0

    def test_cannot_redecide_settled_approval(self, db: Session) -> None:
        queue = ApprovalQueue()
        record = queue.enqueue(
            action_type="issue_refund",
            tool_name="issue_refund",
            entity_id="ord_appr_1",
            customer_id="cust_appr_1",
            amount=12000.0,
            payload={"order_id": "ord_appr_1", "customer_id": "cust_appr_1", "amount": 12000.0},
            db=db,
        )

        queue.reject(approval_id=record.id, reviewer_id="user_1", reason="Denied", db=db)

        # Trying to approve already rejected raises ValueError
        with pytest.raises(ValueError, match="already decided"):
            queue.approve(approval_id=record.id, reviewer_id="user_2", notes="Override", db=db)
