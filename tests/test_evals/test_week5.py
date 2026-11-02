"""
Test Suite for Week 5: Evaluation Metrics, Regression Engine, and CI Gate.
"""

from __future__ import annotations

import io
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base, Customer, Order, Payment, Product
from argvtix.evals.ci_gate import run_ci_gate
from argvtix.evals.metrics import (
    compute_evaluation_summary,
    compute_percentiles,
    detect_language,
)
from argvtix.evals.regression import RegressionEngine
from argvtix.replay.golden import get_golden_case
from argvtix.target_app.llm import MockLLM


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

    # Seed baseline entities
    c1 = Customer(id="1", name="Rohan Das", email="rohan@example.com")
    session.add(c1)

    p1 = Product(id="1", sku="SKU-001", title="BoAt Headphones", price=1200.0, inventory_count=20)
    session.add(p1)

    o1 = Order(id="1", customer_id="1", status="delivered", total_amount=1200.0)
    session.add(o1)

    pay1 = Payment(
        id="1", order_id="1", customer_id="1", amount=1200.0, method="upi", status="succeeded"
    )
    session.add(pay1)
    session.commit()

    yield session
    session.close()


class FlawedCandidateLLM:
    """
    Simulates a regression:
    - Breaks on tickets that contain Hindi keywords (misclassifies as 'unknown').
    """

    def __init__(self, break_hinglish: bool = True) -> None:
        self.break_hinglish = break_hinglish
        self._base = MockLLM()

    def call(self, prompt: str) -> str:
        p = prompt.lower()
        if "intent classifier" in p or "classify the following" in p:
            ticket_part = p.split("customer ticket:")[-1] if "customer ticket:" in p else p
            # If regression is active, break any Hinglish/Hindi tickets
            if self.break_hinglish and any(
                k in ticket_part for k in ("karo", "chahiye", "mera", "batao")
            ):
                return json.dumps(
                    {
                        "intent": "unknown",
                        "order_id": None,
                        "amount": None,
                        "confidence": 0.2,
                    }
                )
        return self._base.call(prompt)


# ---------------------------------------------------------------------------
# Metrics Unit Tests
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_language_detection(self):
        assert detect_language("Please refund my order 102") == "en"
        assert detect_language("Order 101 ka refund chahiye mujhe") == "hinglish"
        assert detect_language("मेरा ऑर्डर रद्द करें") == "hi"

    def test_percentiles_calculation(self):
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        p50, p90, p95 = compute_percentiles(latencies)
        assert p50 == 55.0
        assert p90 == 91.0
        assert p95 == 95.5

    def test_percentiles_empty(self):
        p50, p90, p95 = compute_percentiles([])
        assert p50 == 0.0
        assert p90 == 0.0
        assert p95 == 0.0

    def test_evaluation_summary_computation(self):
        items = [
            {
                "workflow": "refund",
                "ticket_text": "Order refund chahiye",
                "expected_intent": "refund",
                "actual_intent": "refund",
                "expected_guard": "allow",
                "actual_guard": "allow",
                "expected_tool": "issue_refund",
                "actual_tool": "issue_refund",
                "latency_ms": 25.0,
                "cost_usd": 0.0001,
            },
            {
                "workflow": "refund",
                "ticket_text": "Wrong customer refund",
                "expected_intent": "refund",
                "actual_intent": "refund",
                "expected_guard": "block",
                "actual_guard": "block",
                "expected_tool": None,
                "actual_tool": None,
                "latency_ms": 30.0,
                "cost_usd": 0.0001,
            },
            {
                "workflow": "cancel",
                "ticket_text": "Cancel my order please",
                "expected_intent": "cancel_order",
                "actual_intent": "unknown",  # MISMATCH
                "expected_guard": "allow",
                "actual_guard": "allow",
                "expected_tool": "cancel_order",
                "actual_tool": None,
                "latency_ms": 35.0,
                "cost_usd": 0.0001,
            },
        ]
        summary = compute_evaluation_summary(items)
        assert summary.total_evals == 3
        assert summary.intent_accuracy == 66.7
        assert summary.guard_alignment == 100.0
        assert summary.overall_accuracy == 66.7
        assert "refund" in summary.workflow_breakdown


# ---------------------------------------------------------------------------
# Regression Engine Tests
# ---------------------------------------------------------------------------


class TestRegressionEngine:
    def test_identical_configs_have_zero_delta(self, db):
        cases = [
            get_golden_case("gold_bal_026"),
            get_golden_case("gold_bal_027"),
        ]
        cases = [c for c in cases if c is not None]

        engine = RegressionEngine(db=db)
        base_llm = MockLLM()
        cand_llm = MockLLM()

        report = engine.compare(
            baseline_llm=base_llm,
            candidate_llm=cand_llm,
            cases=cases,
        )
        assert report.accuracy_delta == 0.0
        assert len(report.what_got_worse) == 0
        assert len(report.what_got_better) == 0
        assert report.verdict == "PASSED"

    def test_regression_detected_when_candidate_drops_hindi(self, db):
        # Case with Hinglish keyword 'mera': 'Mera wallet balance kitna bacha hai?'
        case = get_golden_case("gold_bal_026")
        assert case is not None

        engine = RegressionEngine(db=db)
        base_llm = MockLLM()
        flawed_llm = FlawedCandidateLLM(break_hinglish=True)

        report = engine.compare(
            baseline_llm=base_llm,
            candidate_llm=flawed_llm,
            cases=[case],
        )

        assert len(report.what_got_worse) == 1
        assert report.what_got_worse[0].case_id == "gold_bal_026"
        assert report.has_critical_regression is True
        assert report.verdict == "FAILED_REGRESSION"


# ---------------------------------------------------------------------------
# CI Evaluation Gate Tests
# ---------------------------------------------------------------------------


class TestCIEvaluationGate:
    def test_ci_gate_passes_on_healthy_candidate(self, db):
        base_llm = MockLLM()
        cand_llm = MockLLM()

        out = io.StringIO()
        code = run_ci_gate(
            db=db,
            baseline_llm=base_llm,
            candidate_llm=cand_llm,
            max_drop_allowed=5.0,
            out=out,
        )
        output_str = out.getvalue()
        assert code == 0
        assert "CI GATE PASSED" in output_str

    def test_ci_gate_blocks_on_flawed_candidate(self, db):
        base_llm = MockLLM()
        flawed_llm = FlawedCandidateLLM(break_hinglish=True)

        out = io.StringIO()
        code = run_ci_gate(
            db=db,
            baseline_llm=base_llm,
            candidate_llm=flawed_llm,
            max_drop_allowed=5.0,
            out=out,
        )
        output_str = out.getvalue()
        assert code == 1
        assert "CI GATE FAILED" in output_str
        assert "BLOCKED" in output_str
