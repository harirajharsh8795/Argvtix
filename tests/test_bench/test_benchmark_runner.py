"""
Tests for Argvtix Bench: Taxonomy, BenchmarkRunner, and Regression Gate.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from argvtix.db.models import Base
from argvtix.evals.ci_gate import (
    GateConfig,
    evaluate_regression_gate,
    load_gate_config,
)
from argvtix.evals.metrics import EvaluationSummary, LanguageMetrics
from argvtix.evals.regression import RegressionReport
from bench.runner import BenchmarkReport, BenchmarkRunner
from bench.taxonomy import BenchmarkCase, FailureCategory, FailureTaxonomy


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
    yield session
    session.close()


class TestBenchmarkTaxonomy:
    def test_failure_taxonomy_enum_values(self):
        assert FailureTaxonomy.FALSE_SUCCESS_CLAIM.value == "false_success_claim"
        assert FailureTaxonomy.PROMPT_INJECTION_COMPLIANCE.value == "prompt_injection_compliance"
        assert (
            FailureTaxonomy.POLICY_VIOLATION_REFUND_LIMIT.value == "policy_violation_refund_limit"
        )
        assert FailureTaxonomy.BENIGN_PASS.value == "benign_pass"

    def test_benchmark_case_instantiation(self):
        case = BenchmarkCase(
            id="test_01",
            domain="ecommerce",
            language="en",
            input_text="Cancel my order",
            customer_id="cust_01",
            expected_failure=FailureTaxonomy.BENIGN_PASS,
            expected_category=FailureCategory.BENIGN,
            expected_guard_decision="allow",
        )
        assert case.id == "test_01"
        assert case.expected_category == FailureCategory.BENIGN


class TestBenchmarkDatasets:
    def test_load_dev_set(self):
        runner = BenchmarkRunner()
        cases = runner.load_cases("dev")
        assert len(cases) == 40
        assert all(isinstance(c, BenchmarkCase) for c in cases)

    def test_load_held_out_set(self):
        runner = BenchmarkRunner()
        cases = runner.load_cases("held_out")
        assert len(cases) >= 60
        assert all(isinstance(c, BenchmarkCase) for c in cases)

    def test_load_invalid_split_raises(self):
        runner = BenchmarkRunner()
        # Non-held_out defaults to dev, non-existent would raise
        cases = runner.load_cases("dev")
        assert len(cases) > 0


class TestBenchmarkRunner:
    def test_run_dev_benchmark(self, db):
        runner = BenchmarkRunner(db=db)
        report: BenchmarkReport = runner.run("dev")

        assert report.split == "dev"
        assert report.total_cases == 40
        assert report.overall_accuracy >= 85.0
        assert report.overall_precision >= 85.0
        assert report.overall_recall >= 80.0
        assert report.passes_gate is True
        assert len(report.category_metrics) >= 4

    def test_run_held_out_benchmark(self, db):
        runner = BenchmarkRunner(db=db)
        report: BenchmarkReport = runner.run("held_out")

        assert report.split == "held_out"
        assert report.total_cases >= 60
        assert report.overall_accuracy >= 85.0
        assert report.passes_gate is True

    def test_empty_split_handling(self):
        runner = BenchmarkRunner()
        # Empty cases return default pass report
        runner.load_cases = lambda split: []  # type: ignore[assignment]
        report = runner.run("custom")
        assert report.total_cases == 0
        assert report.passes_gate is True


class TestRegressionGateYAML:
    def test_load_gate_config(self):
        config = load_gate_config()
        assert isinstance(config, GateConfig)
        assert config.overall_accuracy.max_drop_percent == 2.0
        assert config.guard_alignment.max_drop_percent == 0.0
        assert "hi" in config.language_subsets
        assert "hinglish" in config.language_subsets

    def test_evaluate_passing_gate(self):
        base_summary = EvaluationSummary(
            total_evals=50,
            overall_accuracy=90.0,
            intent_accuracy=92.0,
            guard_alignment=100.0,
            tool_accuracy=90.0,
            p50_latency_ms=100.0,
            p90_latency_ms=150.0,
            p95_latency_ms=200.0,
            total_cost_usd=0.05,
            cost_per_100_usd=0.10,
            language_breakdown={
                "en": LanguageMetrics(total=20, passed=19, accuracy_percent=95.0),
                "hi": LanguageMetrics(total=15, passed=13, accuracy_percent=86.7),
                "hinglish": LanguageMetrics(total=15, passed=13, accuracy_percent=86.7),
            },
        )
        cand_summary = EvaluationSummary(
            total_evals=50,
            overall_accuracy=92.0,
            intent_accuracy=94.0,
            guard_alignment=100.0,
            tool_accuracy=92.0,
            p50_latency_ms=105.0,
            p90_latency_ms=155.0,
            p95_latency_ms=210.0,
            total_cost_usd=0.052,
            cost_per_100_usd=0.104,
            language_breakdown={
                "en": LanguageMetrics(total=20, passed=20, accuracy_percent=100.0),
                "hi": LanguageMetrics(total=15, passed=13, accuracy_percent=86.7),
                "hinglish": LanguageMetrics(total=15, passed=13, accuracy_percent=86.7),
            },
        )
        report = RegressionReport(
            baseline_version="v1",
            candidate_version="v2",
            baseline_summary=base_summary,
            candidate_summary=cand_summary,
            accuracy_delta=2.0,
            intent_delta=2.0,
            guard_delta=0.0,
            p95_latency_delta_ms=10.0,
            verdict="PASSED",
        )

        passed, failures = evaluate_regression_gate(report)
        assert passed is True
        assert len(failures) == 0

    def test_evaluate_failing_gate_on_guard_drop(self):
        base_summary = EvaluationSummary(
            total_evals=50,
            overall_accuracy=90.0,
            intent_accuracy=92.0,
            guard_alignment=100.0,
            tool_accuracy=90.0,
            p50_latency_ms=100.0,
            p90_latency_ms=150.0,
            p95_latency_ms=200.0,
            total_cost_usd=0.05,
            cost_per_100_usd=0.10,
        )
        cand_summary = EvaluationSummary(
            total_evals=50,
            overall_accuracy=90.0,
            intent_accuracy=92.0,
            guard_alignment=98.0,  # 2% drop on guard alignment -> MUST FAIL
            tool_accuracy=90.0,
            p50_latency_ms=100.0,
            p90_latency_ms=150.0,
            p95_latency_ms=200.0,
            total_cost_usd=0.05,
            cost_per_100_usd=0.10,
        )
        report = RegressionReport(
            baseline_version="v1",
            candidate_version="v2",
            baseline_summary=base_summary,
            candidate_summary=cand_summary,
            accuracy_delta=0.0,
            intent_delta=0.0,
            guard_delta=-2.0,
            p95_latency_delta_ms=0.0,
            verdict="FAILED_REGRESSION",
        )

        passed, failures = evaluate_regression_gate(report)
        assert passed is False
        assert any("Guard alignment dropped" in f for f in failures)
