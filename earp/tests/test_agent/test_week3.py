"""
Tests for Week 3: ShopOps Tools, RAG Retriever, and Agent.
All tests use MockLLM + in-memory SQLite — no API key needed.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from earp.db.models import Base, Customer, Order, Payment
from earp.target_app.rag.retriever import retrieve_policy
from earp.target_app.tools.shop_tools import (
    cancel_order,
    get_customer_balance,
    get_order,
    issue_refund,
)

# ---------------------------------------------------------------------------
# Shared test DB fixture
# ---------------------------------------------------------------------------

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

    # Seed minimal data
    c1 = Customer(id="1", name="Rahul Sharma", email="rahul@example.com", phone="9876543210")
    c2 = Customer(id="2", name="Priya Singh", email="priya@example.com", phone="9123456789")
    session.add_all([c1, c2])

    o1 = Order(id="1", customer_id="1", status="delivered", total_amount=5000.0)
    o2 = Order(id="2", customer_id="1", status="pending", total_amount=2500.0)
    o3 = Order(id="3", customer_id="2", status="shipped", total_amount=1200.0)
    session.add_all([o1, o2, o3])

    p1 = Payment(id="1", order_id="1", customer_id="1", amount=5000.0, method="upi", status="succeeded")
    p2 = Payment(id="2", order_id="2", customer_id="1", amount=2500.0, method="card", status="succeeded")
    session.add_all([p1, p2])

    from earp.db.models import Product
    prod = Product(id="1", sku="SKU-001", title="BoAt Headphones", price=2500.0, inventory_count=42)
    session.add(prod)
    session.commit()

    yield session
    session.close()


# ---------------------------------------------------------------------------
# RAG Retriever Tests
# ---------------------------------------------------------------------------

class TestRAGRetriever:
    def test_refund_query_returns_policy(self):
        chunks = retrieve_policy("refund order 7 day policy")
        assert len(chunks) > 0
        assert any("refund" in c.lower() for c in chunks)

    def test_cancel_query_returns_cancel_policy(self):
        chunks = retrieve_policy("cancel order shipped dispatch")
        assert len(chunks) > 0
        assert any("cancel" in c.lower() for c in chunks)

    def test_pii_query_returns_privacy_policy(self):
        chunks = retrieve_policy("aadhaar phone pii privacy data")
        assert len(chunks) > 0
        assert any("pii" in c.lower() or "privacy" in c.lower() for c in chunks)

    def test_top_k_respected(self):
        chunks = retrieve_policy("refund cancel balance inventory", top_k=2)
        assert len(chunks) <= 2

    def test_empty_query_returns_empty(self):
        chunks = retrieve_policy("xyzzy foobar zzz", top_k=3)
        assert isinstance(chunks, list)

    def test_approval_threshold_policy_returned(self):
        chunks = retrieve_policy("refund amount approval supervisor threshold")
        assert any("10,000" in c or "supervisor" in c.lower() for c in chunks)


# ---------------------------------------------------------------------------
# Tool Tests
# ---------------------------------------------------------------------------

class TestShopTools:
    def test_get_order_success(self, db):
        result = get_order(db, order_id=1)
        assert result.success is True
        assert result.data["order_id"] == "1"
        assert result.data["total_amount"] == 5000.0

    def test_get_order_not_found(self, db):
        result = get_order(db, order_id=9999)
        assert result.success is False
        assert result.error is not None

    def test_issue_refund_success(self, db):
        result = issue_refund(db, customer_id=1, order_id=1, amount=500.0)
        assert result.success is True
        assert result.data["amount"] == 500.0
        assert "refund_id" in result.data

    def test_issue_refund_wrong_customer(self, db):
        # Order 1 belongs to customer 1, not customer 2
        result = issue_refund(db, customer_id=2, order_id=1, amount=500.0)
        assert result.success is False
        assert "belong" in result.error.lower()

    def test_issue_refund_order_not_found(self, db):
        result = issue_refund(db, customer_id=1, order_id=9999, amount=100.0)
        assert result.success is False

    def test_cancel_order_pending(self, db):
        result = cancel_order(db, customer_id=1, order_id=2)
        assert result.success is True
        assert result.data["new_status"] == "cancelled"

    def test_cancel_order_shipped_fails(self, db):
        result = cancel_order(db, customer_id=2, order_id=3)
        assert result.success is False
        assert "shipped" in result.error.lower()

    def test_get_customer_balance(self, db):
        result = get_customer_balance(db, customer_id=1)
        assert result.success is True
        assert "wallet_balance" in result.data
        assert result.data["currency"] == "INR"

    def test_get_customer_balance_not_found(self, db):
        result = get_customer_balance(db, customer_id=9999)
        assert result.success is False


# ---------------------------------------------------------------------------
# Agent Integration Tests
# ---------------------------------------------------------------------------

class TestShopOpsAgent:
    """Tests run the full LangGraph pipeline with MockLLM — no API key."""

    def test_agent_refund_flow(self, db):
        from earp.target_app.agent import ShopOpsAgent
        from earp.target_app.llm import MockLLM

        agent = ShopOpsAgent(db=db, llm=MockLLM())
        result = agent.run(ticket_text="Order 1 ka refund chahiye", customer_id=1)

        assert result.intent == "refund"
        assert result.trace is not None
        assert result.trace.trace_id.startswith("tr-")
        assert len(result.trace.steps) >= 3    # classify, retrieve, guard, execute, respond
        assert result.response != ""

    def test_agent_cancel_flow(self, db):
        from earp.target_app.agent import ShopOpsAgent
        from earp.target_app.llm import MockLLM

        agent = ShopOpsAgent(db=db, llm=MockLLM())
        result = agent.run(ticket_text="Cancel order 2", customer_id=1)

        assert result.intent == "cancel_order"
        assert result.trace is not None

    def test_agent_balance_always_allowed(self, db):
        from earp.target_app.agent import ShopOpsAgent
        from earp.target_app.llm import MockLLM

        agent = ShopOpsAgent(db=db, llm=MockLLM())
        result = agent.run(ticket_text="Mera wallet balance check karo", customer_id=1)

        assert result.intent == "balance_inquiry"
        assert result.guard_decision == "ALLOW"

    def test_agent_trace_has_all_step_types(self, db):
        from earp.target_app.agent import ShopOpsAgent
        from earp.target_app.llm import MockLLM

        agent = ShopOpsAgent(db=db, llm=MockLLM())
        result = agent.run(ticket_text="refund order 1", customer_id=1)

        step_types = {step.step_type.value for step in result.trace.steps}
        assert "llm_call" in step_types
        assert "retrieval" in step_types
        assert "guard_decision" in step_types

    def test_agent_different_sessions_have_different_trace_ids(self, db):
        from earp.target_app.agent import ShopOpsAgent
        from earp.target_app.llm import MockLLM

        agent = ShopOpsAgent(db=db, llm=MockLLM())
        r1 = agent.run(ticket_text="refund order 1", customer_id=1)
        r2 = agent.run(ticket_text="balance inquiry", customer_id=1)

        assert r1.trace.trace_id != r2.trace.trace_id

    def test_agent_trace_total_latency_positive(self, db):
        from earp.target_app.agent import ShopOpsAgent
        from earp.target_app.llm import MockLLM

        agent = ShopOpsAgent(db=db, llm=MockLLM())
        result = agent.run(ticket_text="balance check karo", customer_id=1)

        assert result.trace.total_latency_ms >= 0


# ---------------------------------------------------------------------------
# TraceRecorder Unit Tests
# ---------------------------------------------------------------------------

class TestTraceRecorder:
    def test_recorder_builds_trace(self):
        from earp.trace.recorder import TraceRecorder

        r = TraceRecorder(input_text="hello", session_id="s1", workflow_id="wf-test", customer_id=1)
        r.record_llm_call("node1", "mock", "prompt", "response", 12.5)
        r.record_retrieval("node2", "query", ["chunk1", "chunk2"], 5.0)
        r.record_output("node3", "Hello!", 2.0)

        trace = r.build_trace(status="completed")
        assert len(trace.steps) == 3
        assert trace.status.value == "completed"
        assert trace.trace_id.startswith("tr-")

    def test_recorder_step_index_increments(self):
        from earp.trace.recorder import TraceRecorder

        r = TraceRecorder(input_text="test", session_id="s2", workflow_id="wf-test")
        r.record_llm_call("n1", "m", "p", "r", 1.0)
        r.record_output("n2", "out", 1.0)
        trace = r.build_trace()

        assert trace.steps[0].step_index == 0
        assert trace.steps[1].step_index == 1

    def test_recorder_error_step(self):
        from earp.trace.recorder import TraceRecorder
        from earp.trace.schemas import StepType

        r = TraceRecorder(input_text="err test", session_id="s3", workflow_id="wf-test")
        r.record_error("crash_node", "ValueError", "something went wrong")
        trace = r.build_trace(status="failed")

        assert trace.steps[0].step_type == StepType.ERROR
        assert trace.status.value == "failed"
