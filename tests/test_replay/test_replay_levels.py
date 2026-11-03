"""
Unit Tests for Replay Levels L0-L3 and Determinism-Rate Metrics (Step 4 Item 11).

Validates:
1. ReplayLevel L0: Fresh live execution carrying reproducibility class (FRESH/PARTIAL).
2. ReplayLevel L1: Tool results stubbing from historical trace steps without live DB writes.
3. ReplayLevel L2: Tool + Retrieval stubbing + model params/seed pinned (DETERMINISTIC).
4. ReplayLevel L3: State snapshot restoration + L2 stubbing.
5. Every replay result carries a valid ReproducibilityClass (deterministic, partial, fresh).
6. Determinism-rate metric computation across batch replay suites.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, Customer, Order, Payment, Product
from argvtix.replay.levels import (
    DeterminismReport,
    LevelReplayResult,
    LevelReplayRunner,
    ReplayLevel,
    ReproducibilityClass,
    StateSnapshot,
    compute_determinism_rate,
)
from argvtix.target_app.llm import MockLLM
from argvtix.trace.schemas import (
    GuardDecision,
    GuardDecisionData,
    LLMCallData,
    OutputData,
    RetrievalData,
    StepType,
    ToolCallData,
    Trace,
    TraceStatus,
    TraceStep,
)


@pytest.fixture()
def replay_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    c = Customer(id="1", name="Aarav Gupta", email="aarav@example.com", phone="9876543210")
    session.add(c)

    p = Product(id="1", sku="SKU-001", title="BoAt Headphones", price=1200.0, inventory_count=20)
    session.add(p)

    o = Order(id="1", customer_id="1", status="delivered", total_amount=1200.0)
    session.add(o)

    pay = Payment(
        id="1", order_id="1", customer_id="1", amount=1200.0, method="upi", status="succeeded"
    )
    session.add(pay)
    session.commit()

    yield session
    session.close()


@pytest.fixture()
def sample_trace() -> Trace:
    """Fixture providing a realistic historical trace with LLM, retrieval, guard, and tool steps."""
    return Trace(
        trace_id="tr-sample-001",
        session_id="sess-001",
        customer_id="1",
        input_text="Order 1 ka refund chahiye",
        input_language="hinglish",
        prompt_version="v1",
        model_version="gemini-2.0-flash",
        status=TraceStatus.COMPLETED,
        tags=["refund"],
        metadata={"workflow_type": "refund", "intent": "refund"},
        steps=[
            TraceStep(
                step_id="st-01",
                step_index=0,
                step_type=StepType.LLM_CALL,
                duration_ms=12.0,
                llm_call=LLMCallData(
                    model="gemini-2.0-flash",
                    prompt_version="v1",
                    input_text="Classify intent",
                    output_text='{"intent": "refund", "order_id": 1, "amount": 1200.0, "confidence": 0.95}',
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    node="classify_intent",
                ),
            ),
            TraceStep(
                step_id="st-02",
                step_index=1,
                step_type=StepType.RETRIEVAL,
                duration_ms=5.0,
                retrieval=RetrievalData(
                    query="refund Order 1",
                    chunk_ids=["chk-1"],
                    retrieved_chunks=["Return policy: Items can be refunded within 7 days."],
                    scores=[1.0],
                    method="bm25",
                ),
            ),
            TraceStep(
                step_id="st-03",
                step_index=2,
                step_type=StepType.GUARD_DECISION,
                duration_ms=4.0,
                guard_decision=GuardDecisionData(
                    action="issue_refund",
                    entity_id="1",
                    decision=GuardDecision.ALLOW,
                    reasons=["Order ownership verified"],
                ),
            ),
            TraceStep(
                step_id="st-04",
                step_index=3,
                step_type=StepType.TOOL_CALL,
                duration_ms=18.0,
                tool_call=ToolCallData(
                    tool_name="issue_refund",
                    tool_args={"customer_id": 1, "order_id": 1, "amount": 1200.0},
                    tool_result={"refund_id": "ref-101", "status": "completed", "amount": 1200.0},
                    is_success=True,
                ),
            ),
            TraceStep(
                step_id="st-05",
                step_index=4,
                step_type=StepType.OUTPUT,
                duration_ms=2.0,
                output=OutputData(
                    response_text="Refund of 1200 rupees for order 1 has been issued.",
                ),
            ),
        ],
    )


class TestReplayLevels:
    """Validates each replay isolation level and reproducibility classification."""

    def test_replay_level_l0_fresh_execution(self, replay_db, sample_trace: Trace) -> None:
        """Level L0 executes live against tools without stubbing."""
        runner = LevelReplayRunner(db=replay_db, default_llm=MockLLM())
        result: LevelReplayResult = runner.replay(sample_trace, level=ReplayLevel.L0)

        assert result.trace_id == "tr-sample-001"
        assert result.replay_level == ReplayLevel.L0
        assert result.reproducibility_class in (
            ReproducibilityClass.FRESH,
            ReproducibilityClass.PARTIAL,
            ReproducibilityClass.DETERMINISTIC,
        )
        assert result.original_guard == "allow"
        assert result.replayed_guard == "allow"
        assert result.is_identical_guard is True
        assert result.determinism_score >= 0.5

    def test_replay_level_l1_tool_stubbed(self, replay_db, sample_trace: Trace) -> None:
        """Level L1 stubs tool results using recorded trace outputs without live database writes."""
        runner = LevelReplayRunner(db=replay_db, default_llm=MockLLM())
        result: LevelReplayResult = runner.replay(sample_trace, level=ReplayLevel.L1)

        assert result.replay_level == ReplayLevel.L1
        assert result.is_identical_guard is True
        assert result.tool_calls_match is True
        assert result.reproducibility_class in (
            ReproducibilityClass.PARTIAL,
            ReproducibilityClass.DETERMINISTIC,
        )

    def test_replay_level_l2_tool_and_retrieval_and_model_pinned(
        self, replay_db, sample_trace: Trace
    ) -> None:
        """Level L2 stubs tool results, stubs retrieval chunks, and pins model parameters & seed."""
        runner = LevelReplayRunner(db=replay_db, default_llm=MockLLM())
        result: LevelReplayResult = runner.replay(sample_trace, level=ReplayLevel.L2)

        assert result.replay_level == ReplayLevel.L2
        assert result.is_identical_guard is True
        assert result.is_identical_intent is True
        assert result.tool_calls_match is True
        assert result.reproducibility_class in (
            ReproducibilityClass.DETERMINISTIC,
            ReproducibilityClass.PARTIAL,
        )
        assert result.determinism_score >= 0.75

    def test_replay_level_l3_state_snapshot_restore(self, replay_db, sample_trace: Trace) -> None:
        """Level L3 restores the pre-execution database snapshot and executes L2 stubbing."""
        # Mutate order status in DB to simulate dirty state
        order = replay_db.query(Order).filter_by(id="1").first()
        order.status = "cancelled"
        replay_db.commit()

        snapshot = StateSnapshot(
            entity_id="1",
            entity_type="order",
            status="delivered",
            amount=1200.0,
        )

        runner = LevelReplayRunner(db=replay_db, default_llm=MockLLM())
        result: LevelReplayResult = runner.replay(
            sample_trace, level=ReplayLevel.L3, state_snapshot=snapshot
        )

        assert result.replay_level == ReplayLevel.L3
        assert result.is_identical_guard is True
        # Verify order status was restored in the database
        refreshed = replay_db.query(Order).filter_by(id="1").first()
        assert refreshed.status == "delivered"

    def test_reproducibility_class_enumeration(self) -> None:
        """Ensures all 3 reproducibility classes are valid."""
        assert ReproducibilityClass.DETERMINISTIC.value == "deterministic"
        assert ReproducibilityClass.PARTIAL.value == "partial"
        assert ReproducibilityClass.FRESH.value == "fresh"

    def test_determinism_rate_metric_computation(self) -> None:
        """Computes determinism_rate as a percentage of DETERMINISTIC replays."""
        r1 = LevelReplayResult(
            trace_id="t1",
            replay_level=ReplayLevel.L2,
            reproducibility_class=ReproducibilityClass.DETERMINISTIC,
            is_identical_guard=True,
            is_identical_intent=True,
            is_identical_output=True,
            tool_calls_match=True,
            original_guard="allow",
            replayed_guard="allow",
            determinism_score=1.0,
        )
        r2 = LevelReplayResult(
            trace_id="t2",
            replay_level=ReplayLevel.L2,
            reproducibility_class=ReproducibilityClass.DETERMINISTIC,
            is_identical_guard=True,
            is_identical_intent=True,
            is_identical_output=True,
            tool_calls_match=True,
            original_guard="allow",
            replayed_guard="allow",
            determinism_score=1.0,
        )
        r3 = LevelReplayResult(
            trace_id="t3",
            replay_level=ReplayLevel.L2,
            reproducibility_class=ReproducibilityClass.PARTIAL,
            is_identical_guard=True,
            is_identical_intent=True,
            is_identical_output=False,
            tool_calls_match=True,
            original_guard="allow",
            replayed_guard="allow",
            determinism_score=0.75,
        )

        # 2 out of 3 = 66.67%
        rate = compute_determinism_rate([r1, r2, r3])
        assert rate == 66.67

        # 100% on empty or all deterministic
        assert compute_determinism_rate([]) == 100.0
        assert compute_determinism_rate([r1, r2]) == 100.0

    def test_batch_replay_suite_report(self, replay_db, sample_trace: Trace) -> None:
        """Runs batch suite and produces a DeterminismReport."""
        runner = LevelReplayRunner(db=replay_db, default_llm=MockLLM())
        report: DeterminismReport = runner.run_suite([sample_trace], level=ReplayLevel.L2)

        assert report.total_replays == 1
        assert report.replay_level == ReplayLevel.L2
        assert report.determinism_rate >= 0.0
        assert len(report.results) == 1
        assert report.results[0].reproducibility_class is not None
