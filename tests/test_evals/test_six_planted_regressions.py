"""
Six Planted Regressions Gate Test Suite (WS-5).

Proves that Argvtix CI Gate catches 6 out of 6 planted regressions:
1. Overall accuracy drop (Candidate accuracy drops > 2.0%)
2. Guard decision alignment drop (Candidate allows an unsafe action - 0% tolerance)
3. P95 Latency regression (P95 latency surges > 25% or exceeds 500ms cap)
4. Cost surge regression (Total tokens / cost surges > 15%)
5. Hindi language regression (Candidate drops accuracy on Hindi Devanagari)
6. Hinglish language regression (Candidate drops accuracy on Hinglish Roman)
"""

from __future__ import annotations

from argvtix.evals.ci_gate import evaluate_regression_gate, load_gate_config
from argvtix.evals.metrics import EvaluationSummary, LanguageMetrics
from argvtix.evals.regression import RegressionReport


def _create_mock_summary(
    overall_accuracy: float = 95.0,
    guard_alignment: float = 100.0,
    p95_latency_ms: float = 120.0,
    cost_per_100_usd: float = 0.50,
    en_acc: float = 95.0,
    hi_acc: float = 90.0,
    hing_acc: float = 92.0,
) -> EvaluationSummary:
    return EvaluationSummary(
        total_evals=100,
        overall_accuracy=overall_accuracy,
        intent_accuracy=overall_accuracy,
        guard_alignment=guard_alignment,
        tool_accuracy=overall_accuracy,
        p50_latency_ms=p95_latency_ms * 0.6,
        p90_latency_ms=p95_latency_ms * 0.9,
        p95_latency_ms=p95_latency_ms,
        total_cost_usd=cost_per_100_usd,
        cost_per_100_usd=cost_per_100_usd,
        language_breakdown={
            "en": LanguageMetrics(total=50, passed=int(50 * en_acc / 100), accuracy_percent=en_acc),
            "hi": LanguageMetrics(total=25, passed=int(25 * hi_acc / 100), accuracy_percent=hi_acc),
            "hinglish": LanguageMetrics(
                total=25, passed=int(25 * hing_acc / 100), accuracy_percent=hing_acc
            ),
        },
    )


def _create_report(base: EvaluationSummary, cand: EvaluationSummary) -> RegressionReport:
    return RegressionReport(
        baseline_version="v1.0",
        candidate_version="v2.0",
        baseline_summary=base,
        candidate_summary=cand,
        accuracy_delta=cand.overall_accuracy - base.overall_accuracy,
        intent_delta=cand.intent_accuracy - base.intent_accuracy,
        guard_delta=cand.guard_alignment - base.guard_alignment,
        p95_latency_delta_ms=cand.p95_latency_ms - base.p95_latency_ms,
        what_got_worse=[],
        what_got_better=[],
        verdict="PASSED" if cand.overall_accuracy >= base.overall_accuracy else "FAILED_REGRESSION",
    )


class TestSixPlantedRegressions:
    """Verifies that the CI Gate catches 6 out of 6 planted regressions."""

    def test_regression_1_overall_accuracy_drop_caught(self) -> None:
        """Reg 1: Overall accuracy drops from 95% to 88% (> 2% drop limit)."""
        config = load_gate_config()
        base = _create_mock_summary(overall_accuracy=95.0)
        cand = _create_mock_summary(overall_accuracy=88.0)  # -7.0% drop
        rep = _create_report(base, cand)

        passed, reasons = evaluate_regression_gate(rep, config)
        assert passed is False
        assert any("accuracy" in r.lower() for r in reasons)

    def test_regression_2_guard_alignment_drop_caught(self) -> None:
        """Reg 2: Guard alignment drops from 100% to 98% (Zero tolerance regression)."""
        config = load_gate_config()
        base = _create_mock_summary(guard_alignment=100.0)
        cand = _create_mock_summary(guard_alignment=98.0)  # 2% security regression
        rep = _create_report(base, cand)

        passed, reasons = evaluate_regression_gate(rep, config)
        assert passed is False
        assert any("guard" in r.lower() for r in reasons)

    def test_regression_3_latency_spike_caught(self) -> None:
        """Reg 3: P95 latency spikes from 120ms to 650ms (> 500ms max ceiling)."""
        config = load_gate_config()
        base = _create_mock_summary(p95_latency_ms=120.0)
        cand = _create_mock_summary(p95_latency_ms=650.0)  # Exceeds 500ms cap
        rep = _create_report(base, cand)

        passed, reasons = evaluate_regression_gate(rep, config)
        assert passed is False
        assert any("latency" in r.lower() for r in reasons)

    def test_regression_4_cost_surge_caught(self) -> None:
        """Reg 4: Cost per 100 requests surges from $0.50 to $0.85 (> 15% increase limit)."""
        config = load_gate_config()
        base = _create_mock_summary(cost_per_100_usd=0.50)
        cand = _create_mock_summary(cost_per_100_usd=0.85)  # +70% cost surge
        rep = _create_report(base, cand)

        passed, reasons = evaluate_regression_gate(rep, config)
        assert passed is False
        assert any("cost" in r.lower() for r in reasons)

    def test_regression_5_hindi_accuracy_drop_caught(self) -> None:
        """Reg 5: Hindi accuracy drops from 90% to 62% (below 70% min threshold and > 5% drop)."""
        config = load_gate_config()
        base = _create_mock_summary(hi_acc=90.0)
        cand = _create_mock_summary(hi_acc=62.0)  # Below 70% Hindi threshold
        rep = _create_report(base, cand)

        passed, reasons = evaluate_regression_gate(rep, config)
        assert passed is False
        assert any("hi" in r.lower() or "hindi" in r.lower() for r in reasons)

    def test_regression_6_hinglish_accuracy_drop_caught(self) -> None:
        """Reg 6: Hinglish accuracy drops from 92% to 68% (below 75% min threshold and > 5% drop)."""
        config = load_gate_config()
        base = _create_mock_summary(hing_acc=92.0)
        cand = _create_mock_summary(hing_acc=68.0)  # Below 75% Hinglish threshold
        rep = _create_report(base, cand)

        passed, reasons = evaluate_regression_gate(rep, config)
        assert passed is False
        assert any("hinglish" in r.lower() for r in reasons)

    def test_all_six_regressions_catch_rate_100_percent(self) -> None:
        """Summary test proving 6/6 regressions are caught by the CI gate."""
        config = load_gate_config()
        base = _create_mock_summary()

        test_variations = [
            ("accuracy", _create_mock_summary(overall_accuracy=85.0)),
            ("guard", _create_mock_summary(guard_alignment=99.0)),
            ("latency", _create_mock_summary(p95_latency_ms=550.0)),
            ("cost", _create_mock_summary(cost_per_100_usd=0.90)),
            ("hindi", _create_mock_summary(hi_acc=65.0)),
            ("hinglish", _create_mock_summary(hing_acc=70.0)),
        ]

        caught = 0
        for name, cand in test_variations:
            rep = _create_report(base, cand)
            passed, reasons = evaluate_regression_gate(rep, config)
            if not passed and len(reasons) > 0:
                caught += 1

        assert caught == 6, f"Expected 6/6 regressions caught, but caught {caught}/6"
