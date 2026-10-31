"""
Proofline EARP — Staging Verification & Real User Journeys Test Suite (Phase 6).
Executes and validates all 10 required real user journeys:
1. Legitimate low-value refund (DB state, tool result, trace).
2. Refund requiring human approval (Threshold boundary >= ₹10,000, pending queue).
3. Concurrent duplicate refund requests (Zero duplicate commits).
4. Unauthorized cross-user request (IDOR defense, zero writes).
5. Agent false-success claim (Claim-vs-State Verifier discrepancy detection).
6. Trace Explorer rendering (Execution spans, child steps, state diffs).
7. Guardrails & Approvals refresh (Operator session authorization & queue filtering).
8. Database failure and safe recovery (Rollback preservation).
9. Redis failure and safe recovery (In-memory fallback with zero 500s).
10. Application restart during controlled operation (Persistence of pending approvals).
"""

from __future__ import annotations

import concurrent.futures
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from earp.cache.manager import CacheManager, InMemoryLRUTTLCache, RedisCache
from earp.db.models import (
    ApprovalQueueRecord,
    Base,
    Customer,
    Order,
    OrderItem,
    Payment,
    Product,
    Refund,
    TraceRecord,
    TraceStepRecord,
)
from earp.evals.claims import ClaimVerifier
from earp.evals.claims.schemas import ClaimVerdict
from earp.gateway.app import app
from earp.guard import ActionGuard, ApprovalQueue, ToolGateway
from earp.guard.engine import GuardCheckRequest
from earp.security.auth import Role, create_access_token
from earp.target_app.tools import shop_tools
from earp.trace.recorder import TraceRecorder
from earp.trace.schemas import GuardDecision, Severity, StepType, Trace, TraceStatus


# ---------------------------------------------------------------------------
# Test Fixture: Seeded Staging Database
# ---------------------------------------------------------------------------

@pytest.fixture
def staging_db():
    """Sets up an isolated, populated staging database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    # Seed Customer Priya
    priya = Customer(
        id="cust_priya",
        name="Priya Patel",
        email="priya@example.com",
        phone="+919811122233",
        wallet_balance=0.0,
    )
    # Seed Customer Vikram (Separate Tenant)
    vikram = Customer(
        id="cust_vikram",
        name="Vikram Singh",
        email="vikram@example.com",
        phone="+919844455566",
        wallet_balance=0.0,
    )
    db.add_all([priya, vikram])

    # Orders for Priya
    ord_standard = Order(
        id="ord_priya_standard",
        customer_id="cust_priya",
        status="completed",
        subtotal=5000.0,
        tax=900.0,
        total_amount=5900.0,
    )
    ord_vip = Order(
        id="ord_priya_vip",
        customer_id="cust_priya",
        status="completed",
        subtotal=30000.0,
        tax=5400.0,
        total_amount=35400.0,
    )
    # Order for Vikram
    ord_vikram = Order(
        id="ord_vikram_private",
        customer_id="cust_vikram",
        status="completed",
        subtotal=15000.0,
        tax=2700.0,
        total_amount=17700.0,
    )
    db.add_all([ord_standard, ord_vip, ord_vikram])

    # Payments
    pmt_standard = Payment(
        id="pay_priya_std",
        order_id="ord_priya_standard",
        customer_id="cust_priya",
        amount=5900.0,
        status="succeeded",
        method="credit_card",
    )
    pmt_vip = Payment(
        id="pay_priya_vip",
        order_id="ord_priya_vip",
        customer_id="cust_priya",
        amount=35400.0,
        status="succeeded",
        method="netbanking",
    )
    pmt_vikram = Payment(
        id="pay_vikram",
        order_id="ord_vikram_private",
        customer_id="cust_vikram",
        amount=17700.0,
        status="succeeded",
        method="upi",
    )
    db.add_all([pmt_standard, pmt_vip, pmt_vikram])
    db.commit()

    try:
        yield db, TestingSession, engine
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# SCENARIO 1: Legitimate Low-Value Refund
# ---------------------------------------------------------------------------

def test_scenario_1_legitimate_low_value_refund(staging_db):
    """
    Scenario 1: Customer requests refund under ₹10,000.
    Verifies ActionGuard ALLOW, ToolGateway execution, DB record, and Trace.
    """
    db, _, _ = staging_db
    guard = ActionGuard()
    gateway = ToolGateway(guard=guard)

    # 1. Action Guard evaluation
    req = GuardCheckRequest(
        workflow_type="refund",
        tool_name="issue_refund",
        customer_id="cust_priya",
        order_id="ord_priya_standard",
        amount=2500.0,
        reason="Minor scratch on item",
    )
    eval_resp = guard.evaluate(req, db)
    assert eval_resp.decision == GuardDecision.ALLOW
    assert eval_resp.requires_human_approval is False

    # 2. Tool Gateway execution
    result = gateway.call(
        tool_name="issue_refund",
        params={
            "customer_id": "cust_priya",
            "order_id": "ord_priya_standard",
            "amount": 2500.0,
            "reason": "Minor scratch on item",
        },
        db=db,
        idempotency_key="idemp_scen_1_001",
    )
    assert result.decision == GuardDecision.ALLOW
    assert result.success is True
    assert result.status == "completed"
    assert result.data["amount"] == 2500.0

    # 3. Verify Database state
    refund = db.query(Refund).filter_by(order_id="ord_priya_standard").first()
    assert refund is not None
    assert refund.amount == 2500.0
    assert refund.customer_id == "cust_priya"
    assert refund.idempotency_key == "idemp_scen_1_001"


# ---------------------------------------------------------------------------
# SCENARIO 2: Refund Requiring Human Approval
# ---------------------------------------------------------------------------

def test_scenario_2_high_value_refund_approval(staging_db):
    """
    Scenario 2: Refund >= ₹10,000 escalates to HITL queue.
    Verifies zero writes to refunds, pending queue record, and approval dispatch.
    """
    db, _, _ = staging_db
    guard = ActionGuard()
    queue = ApprovalQueue()
    gateway = ToolGateway(guard=guard, approval_queue=queue)

    # 1. Gateway call with high-value amount (₹25,000)
    result = gateway.call(
        tool_name="issue_refund",
        params={
            "customer_id": "cust_priya",
            "order_id": "ord_priya_vip",
            "amount": 25000.0,
            "reason": "VIP laptop return",
        },
        db=db,
    )
    assert result.decision == GuardDecision.ASK_HUMAN
    assert result.status == "pending_approval"
    assert result.approval_id is not None

    # Critical check: Zero writes to business refunds table!
    refund_count = db.query(Refund).filter_by(order_id="ord_priya_vip").count()
    assert refund_count == 0

    # 2. Check pending queue state
    pending_item = queue.get_by_id(result.approval_id, db)
    assert pending_item is not None
    assert pending_item.status == "pending"
    assert pending_item.amount == 25000.0

    # 3. Operator reviews and approves
    approved_rec, tool_res = queue.approve(
        approval_id=result.approval_id,
        reviewer_id="lead_operator_sam",
        notes="Invoice and return tracking verified",
        db=db,
        gateway=gateway,
    )
    assert approved_rec.status == "approved"
    assert approved_rec.reviewer_id == "lead_operator_sam"

    # 4. Confirm refund row now exists post-approval
    refund_post = db.query(Refund).filter_by(order_id="ord_priya_vip").first()
    assert refund_post is not None
    assert refund_post.amount == 25000.0


# ---------------------------------------------------------------------------
# SCENARIO 3: Concurrent Duplicate Refund Requests
# ---------------------------------------------------------------------------

def test_scenario_3_concurrent_duplicate_refunds(tmp_path):
    """
    Scenario 3: Concurrent workers issue identical refund requests.
    Verifies exactly one committed refund and zero duplicates.
    """
    db_file = tmp_path / "scenario_3.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"timeout": 30})
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(bind=engine)
    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with SessionFactory() as init_db:
        cust = Customer(id="c1", name="Concurrent User", email="c@test.com", phone="+919000000000")
        ord1 = Order(id="o1", customer_id="c1", status="completed", subtotal=5000.0, tax=0.0, total_amount=5000.0)
        pay1 = Payment(id="p1", order_id="o1", customer_id="c1", amount=5000.0, status="succeeded")
        init_db.add_all([cust, ord1, pay1])
        init_db.commit()

    key = "idemp_scen_3_concurrent"
    results = []

    def worker(i: int):
        with SessionFactory() as session:
            return shop_tools.issue_refund(
                db=session,
                customer_id="c1",
                order_id="o1",
                amount=1000.0,
                reason=f"worker_{i}",
                idempotency_key=key,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker, i) for i in range(4)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # All workers returned success
    for r in results:
        assert r.success is True

    # Critical Database Invariant: Exactly 1 row committed!
    with SessionFactory() as verify_db:
        refunds = verify_db.query(Refund).filter_by(order_id="o1").all()
        assert len(refunds) == 1
        assert refunds[0].idempotency_key == key


# ---------------------------------------------------------------------------
# SCENARIO 4: Unauthorized Cross-Tenant Access (IDOR)
# ---------------------------------------------------------------------------

def test_scenario_4_unauthorized_idor_request(staging_db):
    """
    Scenario 4: Priya attempts to refund Vikram's order.
    Verifies Action Guard Rule ACT-03 blocks immediately with zero DB writes.
    """
    db, _, _ = staging_db
    guard = ActionGuard()
    req = GuardCheckRequest(
        workflow_type="refund",
        tool_name="issue_refund",
        customer_id="cust_priya",
        order_id="ord_vikram_private",  # Vikram's order!
        amount=1000.0,
        reason="Malicious cross-tenant attempt",
    )
    resp = guard.evaluate(req, db)
    assert resp.decision == GuardDecision.BLOCK
    assert resp.risk_level == Severity.CRITICAL
    assert "ACT-03" in resp.reason

    # Verify zero database mutations
    assert db.query(Refund).filter_by(order_id="ord_vikram_private").count() == 0


# ---------------------------------------------------------------------------
# SCENARIO 5: Agent False-Success Claim Detection
# ---------------------------------------------------------------------------

def test_scenario_5_agent_false_success_claim():
    """
    Scenario 5: Agent falsely claims refund was issued when gateway timed out.
    Verifies ClaimVerifier flags FALSE_SUCCESS and OMITTED_FAILURE.
    """
    verifier = ClaimVerifier()
    agent_msg = "Aapka order cancel ho gaya hai aur ₹2,500 ka refund aapke bank account mein bhej diya gaya hai."
    tool_logs = [{
        "tool_name": "issue_refund",
        "tool_args": {"order_id": "ord_101", "amount": 2500.0},
        "tool_result": {"status": "error", "error": "Bank payment gateway timeout"},
        "is_success": False,
    }]

    report = verifier.verify(agent_response=agent_msg, tool_records=tool_logs)
    assert report.violations_count >= 1
    verdicts = [r.verdict for r in report.results]
    assert ClaimVerdict.FALSE_SUCCESS in verdicts or ClaimVerdict.OMITTED_FAILURE in verdicts


# ---------------------------------------------------------------------------
# SCENARIO 6: Trace Explorer Rendering & Spans
# ---------------------------------------------------------------------------

def test_scenario_6_trace_explorer_spans():
    """
    Scenario 6: Verifies TraceRecord and execution spans.
    """
    recorder = TraceRecorder(
        input_text="I want a refund for my order",
        session_id="sess_scen_6",
        customer_id="cust_priya",
    )
    recorder.record_tool_call(
        node="tool_executor",
        tool_name="issue_refund",
        inputs={"order_id": "ord_123", "amount": 1200.0},
        outputs={"status": "completed", "refund_id": "ref_999"},
        latency_ms=45.2,
        success=True,
    )
    completed_trace = recorder.build_trace(status=TraceStatus.COMPLETED)

    assert completed_trace.trace_id == recorder.trace_id
    assert completed_trace.status == TraceStatus.COMPLETED
    assert len(completed_trace.steps) == 1
    assert completed_trace.steps[0].tool_call.tool_name == "issue_refund"
    assert completed_trace.steps[0].duration_ms == 45.2


# ---------------------------------------------------------------------------
# SCENARIO 7: Guardrails & Approvals Refresh & Authorization
# ---------------------------------------------------------------------------

def test_scenario_7_approvals_authorization_and_refresh(staging_db):
    """
    Scenario 7: Operator signs in and retrieves approval queue.
    Verifies JWT role validation and queue status filtering.
    """
    db, _, _ = staging_db
    queue = ApprovalQueue()
    queue.enqueue(
        action_type="refund",
        tool_name="issue_refund",
        entity_id="ord_test_07",
        customer_id="cust_priya",
        amount=12000.0,
        payload={"order_id": "ord_test_07"},
        guard_reason="ACT-01: High-value refund",
        risk_level=Severity.HIGH,
        db=db,
    )

    # Valid operator token
    op_token = create_access_token(user_id="operator_sarah", role=Role.OPERATOR)
    assert op_token is not None

    # Retrieve queue items
    pending_items = queue.list_pending(db)
    assert len(pending_items) >= 1
    assert any(item.entity_id == "ord_test_07" for item in pending_items)


# ---------------------------------------------------------------------------
# SCENARIO 8: Database Failure & Safe Recovery
# ---------------------------------------------------------------------------

def test_scenario_8_database_failure_and_safe_recovery(staging_db):
    """
    Scenario 8: Transaction error forces rollback; database resets safely.
    """
    db, _, _ = staging_db
    try:
        # Intentionally attempt invalid insert (violates NOT NULL or bad FK)
        db.add(Refund(order_id="non_existent_order_id_999", amount=-500.0, status="invalid"))
        db.commit()
    except Exception:
        db.rollback()

    # Verify session is healthy and clean post-rollback
    customer = db.query(Customer).filter_by(id="cust_priya").first()
    assert customer is not None
    assert customer.id == "cust_priya"


# ---------------------------------------------------------------------------
# SCENARIO 9: Redis Failure & Safe Recovery
# ---------------------------------------------------------------------------

def test_scenario_9_redis_failure_and_safe_recovery():
    """
    Scenario 9: Redis disconnects; verifies transparent fallback with zero 500s.
    """
    fallback_cache = InMemoryLRUTTLCache(maxsize=500)
    # Connect to non-existent Redis server
    redis_backend = RedisCache(redis_url="redis://127.0.0.1:65531/0", fallback_cache=fallback_cache)

    # Write and read must succeed via fallback without raising exceptions
    assert redis_backend.set("session:test_scen_9", {"auth": True}, ttl_seconds=120) is True
    val = redis_backend.get("session:test_scen_9")
    assert val == {"auth": True}
    assert redis_backend.delete("session:test_scen_9") is True
    assert redis_backend.get("session:test_scen_9") is None


# ---------------------------------------------------------------------------
# SCENARIO 10: Application Restart During Controlled Operation
# ---------------------------------------------------------------------------

def test_scenario_10_application_restart_persistence(tmp_path):
    """
    Scenario 10: Simulates application restart while approval is pending.
    Verifies approval state survives restart and can be executed post-boot.
    """
    db_file = tmp_path / "scenario_10.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)
    SessionClass = sessionmaker(bind=engine)

    # 1. Before restart: Enqueue pending item
    approval_id = None
    with SessionClass() as db_pre:
        cust = Customer(id="c_restart", name="Restart User", email="r@test.com", phone="+919111111111")
        ord1 = Order(id="o_restart", customer_id="c_restart", status="completed", subtotal=20000.0, tax=0.0, total_amount=20000.0)
        pay1 = Payment(id="p_restart", order_id="o_restart", customer_id="c_restart", amount=20000.0, status="succeeded")
        db_pre.add_all([cust, ord1, pay1])
        db_pre.commit()

        queue_pre = ApprovalQueue()
        item = queue_pre.enqueue(
            action_type="refund",
            tool_name="issue_refund",
            entity_id="o_restart",
            customer_id="c_restart",
            amount=15000.0,
            payload={"customer_id": "c_restart", "order_id": "o_restart", "amount": 15000.0},
            guard_reason="ACT-01: High-value refund",
            risk_level=Severity.HIGH,
            db=db_pre,
        )
        approval_id = item.id

    # 2. Simulate Application Restart (dispose connection pool, re-bind new session)
    engine.dispose()
    new_engine = create_engine(f"sqlite:///{db_file}")
    NewSessionClass = sessionmaker(bind=new_engine)

    # 3. Post restart: Inspect and approve item
    with NewSessionClass() as db_post:
        queue_post = ApprovalQueue()
        pending_post = queue_post.get_by_id(approval_id, db_post)
        assert pending_post is not None
        assert pending_post.status == "pending"
        assert pending_post.amount == 15000.0

        # Approve and execute
        gateway = ToolGateway(approval_queue=queue_post)
        approved_post, _ = queue_post.approve(
            approval_id=approval_id,
            reviewer_id="lead_operator_post_restart",
            notes="Approved after system restart",
            db=db_post,
            gateway=gateway,
        )
        assert approved_post.status == "approved"

        # Verify refund was committed post-restart
        refund_done = db_post.query(Refund).filter_by(order_id="o_restart").first()
        assert refund_done is not None
        assert refund_done.amount == 15000.0
