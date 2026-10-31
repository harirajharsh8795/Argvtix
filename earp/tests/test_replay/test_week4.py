"""
Test Suite for Week 4: Trace Store, Golden Dataset, and Replay Engine.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from earp.db.models import Base, Customer, Order, Payment, Product
from earp.replay.engine import ReplayEngine
from earp.replay.golden import (
    GoldenCase,
    filter_golden_cases,
    get_golden_case,
    load_golden_cases,
)
from earp.target_app.llm import MockLLM
from earp.trace.schemas import (
    GuardDecision,
    GuardDecisionData,
    LLMCallData,
    OutputData,
    StepType,
    Trace,
    TraceStatus,
    TraceStep,
)
from earp.trace.store import get_trace, list_trace_records, save_trace


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

    # Seed baseline customer, order, product, payment
    c = Customer(id="1", name="Aarav Gupta", email="aarav@example.com", phone="9876543210")
    session.add(c)

    p = Product(id="1", sku="SKU-001", title="BoAt Headphones", price=1200.0, inventory_count=20)
    session.add(p)

    o = Order(id="1", customer_id="1", status="delivered", total_amount=1200.0)
    session.add(o)

    pay = Payment(id="1", order_id="1", customer_id="1", amount=1200.0, method="upi", status="succeeded")
    session.add(pay)
    session.commit()

    yield session
    session.close()


# ---------------------------------------------------------------------------
# Trace Store Unit Tests
# ---------------------------------------------------------------------------

class TestTraceStore:
    def test_save_and_get_trace(self, db):
        trace = Trace(
            trace_id="tr-test-001",
            session_id="sess-001",
            customer_id="1",
            input_text="Order 1 ka refund chahiye",
            input_language="hinglish",
            prompt_version="v1",
            model_version="gemini-2.0-flash",
            status=TraceStatus.COMPLETED,
            tags=["refund"],
            metadata={"workflow_type": "refund"},
            steps=[
                TraceStep(
                    step_id="st-01",
                    step_index=0,
                    step_type=StepType.LLM_CALL,
                    duration_ms=15.0,
                    llm_call=LLMCallData(
                        model="gemini-2.0-flash",
                        prompt_version="v1",
                        input_text="Classify intent",
                        output_text="refund",
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                    ),
                ),
                TraceStep(
                    step_id="st-02",
                    step_index=1,
                    step_type=StepType.GUARD_DECISION,
                    duration_ms=8.0,
                    guard_decision=GuardDecisionData(
                        action="issue_refund",
                        entity_id="1",
                        decision=GuardDecision.ALLOW,
                        reasons=["Ownership verified"],
                    ),
                ),
                TraceStep(
                    step_id="st-03",
                    step_index=2,
                    step_type=StepType.OUTPUT,
                    duration_ms=2.0,
                    output=OutputData(
                        response_text="Aapka refund approve ho gaya.",
                    ),
                ),
            ],
        )

        record = save_trace(db, trace)
        assert record.id == "tr-test-001"
        assert record.status == "completed"

        fetched = get_trace(db, "tr-test-001")
        assert fetched is not None
        assert fetched.trace_id == "tr-test-001"
        assert len(fetched.steps) == 3
        assert fetched.steps[0].step_type == StepType.LLM_CALL
        assert fetched.steps[1].step_type == StepType.GUARD_DECISION
        assert fetched.steps[2].step_type == StepType.OUTPUT

    def test_duplicate_trace_id_raises_value_error(self, db):
        t1 = Trace(
            trace_id="tr-dup-01",
            input_text="Help",
            prompt_version="v1",
            model_version="gemini-2.0-flash",
        )
        save_trace(db, t1)

        with pytest.raises(ValueError, match="already exists"):
            save_trace(db, t1)

    def test_get_nonexistent_trace_returns_none(self, db):
        assert get_trace(db, "tr-nonexistent") is None

    def test_list_trace_records(self, db):
        t1 = Trace(
            trace_id="tr-list-01",
            input_text="Cancel order",
            prompt_version="v1",
            model_version="gemini-2.0-flash",
            metadata={"workflow_type": "cancel"},
        )
        t2 = Trace(
            trace_id="tr-list-02",
            input_text="Refund order",
            prompt_version="v1",
            model_version="gemini-2.0-flash",
            metadata={"workflow_type": "refund"},
        )
        save_trace(db, t1)
        save_trace(db, t2)

        records = list_trace_records(db, workflow_type="cancel")
        assert len(records) == 1
        assert records[0].id == "tr-list-01"


# ---------------------------------------------------------------------------
# Golden Cases Dataset Tests
# ---------------------------------------------------------------------------

class TestGoldenCases:
    def test_load_all_golden_cases(self):
        cases = load_golden_cases()
        assert len(cases) == 80
        assert all(isinstance(c, GoldenCase) for c in cases)

    def test_get_single_case(self):
        case = get_golden_case("gold_ref_001")
        assert case is not None
        assert case.workflow == "refund"
        assert case.expected_intent == "refund"
        assert case.expected_guard_decision == "allow"

    def test_filter_cases_by_workflow(self):
        refunds = filter_golden_cases(workflow="refund")
        assert len(refunds) == 22
        cancels = filter_golden_cases(workflow="cancel")
        assert len(cancels) == 15
        balances = filter_golden_cases(workflow="balance")
        assert len(balances) == 12

    def test_all_cases_have_valid_expected_decisions(self):
        cases = load_golden_cases()
        valid_decisions = {"allow", "block", "ask_human"}
        for c in cases:
            assert c.expected_guard_decision.lower() in valid_decisions, f"Invalid decision in {c.id}"


# ---------------------------------------------------------------------------
# Replay Engine Tests
# ---------------------------------------------------------------------------

class TestReplayEngine:
    def test_replay_trace(self, db):
        # 1. Save an initial trace
        initial_trace = Trace(
            trace_id="tr-replay-001",
            customer_id="1",
            session_id="sess-rep",
            input_text="Order 1 ka refund chahiye",
            prompt_version="v1",
            model_version="gemini-2.0-flash",
            status=TraceStatus.COMPLETED,
            metadata={"workflow_id": "wf-shopops-support"},
            steps=[
                TraceStep(
                    step_id="st-01",
                    step_index=0,
                    step_type=StepType.GUARD_DECISION,
                    duration_ms=10.0,
                    guard_decision=GuardDecisionData(
                        action="issue_refund",
                        entity_id="1",
                        decision=GuardDecision.ALLOW,
                    ),
                )
            ],
        )
        save_trace(db, initial_trace)

        # 2. Replay with ReplayEngine
        engine = ReplayEngine(db=db, default_llm=MockLLM())
        comp = engine.replay_trace("tr-replay-001")

        assert comp.trace_id == "tr-replay-001"
        assert comp.replayed_trace is not None
        assert comp.replayed_trace.trace_id.startswith("tr-")
        assert isinstance(comp.latency_delta_ms, float)

    def test_replay_golden_case_success(self, db):
        engine = ReplayEngine(db=db, default_llm=MockLLM())
        case = get_golden_case("gold_bal_026")  # wallet balance inquiry
        assert case is not None

        result = engine.replay_case(case)
        assert result.case_id == "gold_bal_026"
        assert result.intent_match is True
        assert result.guard_match is True
        assert result.is_passed is True

    def test_run_golden_suite_subset(self, db):
        engine = ReplayEngine(db=db, default_llm=MockLLM())
        subset = [
            get_golden_case("gold_bal_026"),
            get_golden_case("gold_bal_027"),
        ]
        subset = [c for c in subset if c is not None]

        bench = engine.run_suite(cases=subset)
        assert bench.total_cases == 2
        assert bench.passed_cases >= 1
        assert 0.0 <= bench.accuracy_percent <= 100.0
