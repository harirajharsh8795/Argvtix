"""
Tests for pass^k Reliability Runner and Multi-Trial Flake Rate.

Validates:
1. Unbiased pass@k estimator (Codex / HumanEval formula).
2. pass@1 (average trial accuracy).
3. pass^k (strict consistency: all k trials must pass).
4. Flake rate detection (cases with intermittent success/failure).
5. PassKReport generation and reliability index.
"""

from __future__ import annotations

import pytest

from earp.evals.passk import (
    PassKRunner,
    estimate_pass_at_k,
)


class TestPassKStatistics:
    """Mathematical validation of pass@k estimation."""

    def test_estimator_all_correct(self) -> None:
        # If all samples correct, pass@k must be 1.0
        val = estimate_pass_at_k(num_samples=10, num_correct=10, k=5)
        assert val == 1.0

    def test_estimator_zero_correct(self) -> None:
        # If zero samples correct, pass@k must be 0.0
        val = estimate_pass_at_k(num_samples=10, num_correct=0, k=5)
        assert val == 0.0

    def test_estimator_partial_correct(self) -> None:
        # 5 out of 10 correct, pass@1 should be 0.5, pass@5 should be higher
        p1 = estimate_pass_at_k(num_samples=10, num_correct=5, k=1)
        p5 = estimate_pass_at_k(num_samples=10, num_correct=5, k=5)
        assert round(p1, 2) == 0.50
        assert p5 > p1


class TestPassKRunner:
    """Execution testing for PassKRunner."""

    def test_invalid_k_raises(self) -> None:
        with pytest.raises(ValueError):
            PassKRunner(k=0)

    def test_all_passing_scenarios(self) -> None:
        runner = PassKRunner(k=5)
        cases = [
            ("case_always_true_1", lambda: True),
            ("case_always_true_2", lambda: (True, {"note": "clean"})),
        ]
        report = runner.run(cases)
        assert report.total_cases == 2
        assert report.pass_at_1 == 100.0
        assert report.pass_at_k == 100.0
        assert report.pass_hat_k == 100.0
        assert report.flake_rate == 0.0
        assert report.reliability_index == 100.0
        assert len(report.perfect_case_ids) == 2
        assert len(report.flaky_case_ids) == 0

    def test_all_failing_scenarios(self) -> None:
        runner = PassKRunner(k=5)
        cases = [
            ("case_always_fail", lambda: False),
        ]
        report = runner.run(cases)
        assert report.total_cases == 1
        assert report.pass_at_1 == 0.0
        assert report.pass_at_k == 0.0
        assert report.pass_hat_k == 0.0
        assert report.flake_rate == 0.0
        assert report.reliability_index == 0.0
        assert len(report.failed_case_ids) == 1

    def test_flaky_scenario_detected(self) -> None:
        # Alternates true and false
        counter = {"count": 0}

        def flaky_eval() -> bool:
            counter["count"] += 1
            return counter["count"] % 2 == 1  # trials 1, 3, 5 True (3/5)

        runner = PassKRunner(k=5)
        cases = [
            ("case_flaky_1", flaky_eval),
        ]
        report = runner.run(cases)
        assert report.total_cases == 1
        assert report.pass_at_1 == 60.0  # 3/5 = 60%
        assert report.pass_at_k == 100.0  # at least one succeeded
        assert report.pass_hat_k == 0.0  # NOT all passed (pass^k is 0)
        assert report.flake_rate == 100.0  # this case was flaky
        assert "case_flaky_1" in report.flaky_case_ids

    def test_empty_cases_list(self) -> None:
        runner = PassKRunner(k=3)
        report = runner.run([])
        assert report.total_cases == 0
        assert report.flake_rate == 0.0
        assert report.reliability_index == 100.0
