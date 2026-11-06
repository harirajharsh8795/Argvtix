"""
Unit and negative control tests for Argvtix Regression Gate.
Implements 6 real planted regressions:
1. accuracy_drop (> 2.0% drop) -> GateVerdict.FAIL
2. guard_weakened (policy violations allowed) -> GateVerdict.FAIL
3. hindi_drop (> 3.0% drop) -> GateVerdict.FAIL
4. hinglish_drop (> 3.0% drop) -> GateVerdict.FAIL
5. latency_spike (> 50% p95 spike) -> GateVerdict.REVIEW
6. cost_surge (> 30% cost increase) -> GateVerdict.REVIEW
And 1 clean candidate:
7. clean_candidate -> GateVerdict.PASS
"""

from __future__ import annotations

import copy
from typing import Any

from argvtix.regression.comparator import GateVerdict, evaluate_regression_gate

BASELINE_METRICS: dict[str, Any] = {
    "overall_accuracy_pct": 98.0,
    "state_grounding_recall_pct": 95.0,
    "guard_bypasses_count": 0,
    "guard_fpr_pct": 0.0,
    "hindi_accuracy_pct": 94.0,
    "hinglish_accuracy_pct": 92.0,
    "p95_latency_ms": 120.0,
    "cost_usd_per_1k": 0.015,
}


def test_gate_passes_clean_candidate() -> None:
    """Proves that a candidate meeting or exceeding baseline metrics cleanly passes."""
    clean_candidate = {
        "overall_accuracy_pct": 98.5,
        "state_grounding_recall_pct": 96.0,
        "guard_bypasses_count": 0,
        "guard_fpr_pct": 0.0,
        "hindi_accuracy_pct": 94.5,
        "hinglish_accuracy_pct": 93.0,
        "p95_latency_ms": 115.0,
        "cost_usd_per_1k": 0.014,
    }
    report = evaluate_regression_gate(BASELINE_METRICS, clean_candidate)
    assert report.verdict == GateVerdict.PASS
    assert report.overall_pass is True
    assert len(report.failed_checks) == 0
    assert len(report.review_checks) == 0


def test_gate_fails_on_accuracy_drop() -> None:
    """Planted regression 1: Accuracy drops from 98.0% to 94.0% (-4.0%)."""
    cand = copy.deepcopy(BASELINE_METRICS)
    cand["overall_accuracy_pct"] = 94.0
    report = evaluate_regression_gate(BASELINE_METRICS, cand)
    assert report.verdict == GateVerdict.FAIL
    assert report.overall_pass is False
    assert any(c.check_name == "overall_accuracy" for c in report.failed_checks)


def test_gate_fails_on_guard_weakened() -> None:
    """Planted regression 2: Guard allows 2 unauthorized actions through."""
    cand = copy.deepcopy(BASELINE_METRICS)
    cand["guard_bypasses_count"] = 2
    report = evaluate_regression_gate(BASELINE_METRICS, cand)
    assert report.verdict == GateVerdict.FAIL
    assert report.overall_pass is False
    assert any(c.check_name == "guard_weakened" for c in report.failed_checks)


def test_gate_fails_on_hindi_drop() -> None:
    """Planted regression 3: Hindi accuracy drops from 94.0% to 88.0% (-6.0%)."""
    cand = copy.deepcopy(BASELINE_METRICS)
    cand["hindi_accuracy_pct"] = 88.0
    report = evaluate_regression_gate(BASELINE_METRICS, cand)
    assert report.verdict == GateVerdict.FAIL
    assert report.overall_pass is False
    assert any(c.check_name == "hindi_accuracy" for c in report.failed_checks)


def test_gate_fails_on_hinglish_drop() -> None:
    """Planted regression 4: Hinglish accuracy drops from 92.0% to 85.0% (-7.0%)."""
    cand = copy.deepcopy(BASELINE_METRICS)
    cand["hinglish_accuracy_pct"] = 85.0
    report = evaluate_regression_gate(BASELINE_METRICS, cand)
    assert report.verdict == GateVerdict.FAIL
    assert report.overall_pass is False
    assert any(c.check_name == "hinglish_accuracy" for c in report.failed_checks)


def test_gate_flags_review_on_latency_spike() -> None:
    """Planted regression 5: Latency spikes from 120ms to 250ms (+108%)."""
    cand = copy.deepcopy(BASELINE_METRICS)
    cand["p95_latency_ms"] = 250.0
    report = evaluate_regression_gate(BASELINE_METRICS, cand)
    assert report.verdict == GateVerdict.REVIEW
    assert report.overall_pass is True  # Non-blocking infra review
    assert any(c.check_name == "latency_spike" for c in report.review_checks)


def test_gate_flags_review_on_cost_surge() -> None:
    """Planted regression 6: Cost surges from $0.015 to $0.025 (+66%)."""
    cand = copy.deepcopy(BASELINE_METRICS)
    cand["cost_usd_per_1k"] = 0.025
    report = evaluate_regression_gate(BASELINE_METRICS, cand)
    assert report.verdict == GateVerdict.REVIEW
    assert report.overall_pass is True  # Non-blocking infra review
    assert any(c.check_name == "cost_surge" for c in report.review_checks)
