"""
CI Evaluation Gate — Automated quality & regression gate for GitHub Actions.

Evaluates AI agent candidate against baseline thresholds defined in config/regression_gate.yaml.
Blocks PR merge (exits with code 1) if:
- Overall accuracy drops below threshold (e.g. > 2.0% regression)
- Guard decision alignment drops (0% regression tolerated for security/safety)
- P95 latency exceeds maximum increase or absolute limit
- Cost per 100 requests exceeds maximum increase
- Hindi/Hinglish language accuracy drops below language-specific thresholds
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import TextIO

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import yaml

from earp.evals.regression import RegressionEngine, RegressionReport
from earp.replay.golden import load_golden_cases
from earp.target_app.llm import LLMProtocol

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
DEFAULT_GATE_CONFIG_PATH = CONFIG_DIR / "regression_gate.yaml"


class OverallAccuracyThreshold(BaseModel):
    max_drop_percent: float = 2.0
    min_absolute_accuracy: float = 80.0


class GuardAlignmentThreshold(BaseModel):
    max_drop_percent: float = 0.0
    min_guard_alignment: float = 100.0


class LatencyThreshold(BaseModel):
    max_increase_percent: float = 25.0
    max_absolute_p95_ms: float = 500.0
    min_noise_threshold_ms: float = 50.0


class CostThreshold(BaseModel):
    max_increase_percent: float = 15.0
    max_cost_per_100_usd: float = 5.0


class LanguageThreshold(BaseModel):
    min_accuracy: float = 70.0
    max_drop_percent: float = 5.0


class BenchmarkThreshold(BaseModel):
    min_precision: float = 85.0
    min_recall: float = 80.0
    min_f1: float = 82.0


class GateConfig(BaseModel):
    version: str = "2.0"
    gate_name: str = "production_ci_gate"
    overall_accuracy: OverallAccuracyThreshold = Field(default_factory=OverallAccuracyThreshold)
    guard_alignment: GuardAlignmentThreshold = Field(default_factory=GuardAlignmentThreshold)
    latency: LatencyThreshold = Field(default_factory=LatencyThreshold)
    cost: CostThreshold = Field(default_factory=CostThreshold)
    language_subsets: dict[str, LanguageThreshold] = Field(default_factory=dict)
    benchmark: BenchmarkThreshold = Field(default_factory=BenchmarkThreshold)


def load_gate_config(path: str | Path | None = None) -> GateConfig:
    """Load CI regression gate configuration from YAML file."""
    config_path = Path(path) if path else DEFAULT_GATE_CONFIG_PATH
    if not config_path.exists():
        # Fallback to sensible defaults
        return GateConfig()

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return GateConfig(**data)


def evaluate_regression_gate(
    report: RegressionReport,
    config: GateConfig | None = None,
    enforce_absolute: bool | None = None,
) -> tuple[bool, list[str]]:
    """
    Evaluates a RegressionReport against GateConfig criteria.
    Returns (is_passed, failure_reasons).
    """
    if config is None:
        config = load_gate_config()

    if enforce_absolute is None:
        # Auto-detect: only enforce absolute floors if baseline itself met them
        enforce_absolute = report.baseline_summary.overall_accuracy >= config.overall_accuracy.min_absolute_accuracy

    failures: list[str] = []

    # 1. Overall accuracy checks
    if report.accuracy_delta < -abs(config.overall_accuracy.max_drop_percent):
        failures.append(
            f"Overall accuracy drop {report.accuracy_delta:+.2f}% exceeds max allowed "
            f"-{config.overall_accuracy.max_drop_percent:.2f}%"
        )
    if enforce_absolute and report.candidate_summary.overall_accuracy < config.overall_accuracy.min_absolute_accuracy:
        failures.append(
            f"Candidate overall accuracy {report.candidate_summary.overall_accuracy:.2f}% is below min required "
            f"{config.overall_accuracy.min_absolute_accuracy:.2f}%"
        )

    # 2. Guard alignment checks (Zero tolerance for security/guard regression)
    guard_drop = report.baseline_summary.guard_alignment - report.candidate_summary.guard_alignment
    if guard_drop > config.guard_alignment.max_drop_percent:
        failures.append(
            f"Guard alignment dropped by {guard_drop:.2f}%, violating zero-regression policy "
            f"(max drop {config.guard_alignment.max_drop_percent:.2f}%)"
        )
    if enforce_absolute and report.candidate_summary.guard_alignment < config.guard_alignment.min_guard_alignment:
        failures.append(
            f"Candidate guard alignment {report.candidate_summary.guard_alignment:.2f}% is below required "
            f"{config.guard_alignment.min_guard_alignment:.2f}%"
        )

    # 3. Latency checks
    p95_base = report.baseline_summary.p95_latency_ms
    p95_cand = report.candidate_summary.p95_latency_ms
    if p95_base > 0:
        latency_increase_pct = ((p95_cand - p95_base) / p95_base) * 100.0
        if (
            (p95_cand - p95_base) > config.latency.min_noise_threshold_ms
            and latency_increase_pct > config.latency.max_increase_percent
        ):
            failures.append(
                f"P95 latency increased by {latency_increase_pct:+.1f}%, exceeding max increase "
                f"{config.latency.max_increase_percent:.1f}%"
            )
    if p95_cand > config.latency.max_absolute_p95_ms:
        failures.append(
            f"P95 latency {p95_cand:.1f}ms exceeds absolute ceiling {config.latency.max_absolute_p95_ms:.1f}ms"
        )

    # 4. Cost checks
    cost_base = report.baseline_summary.cost_per_100_usd
    cost_cand = report.candidate_summary.cost_per_100_usd
    if cost_base > 0:
        cost_increase_pct = ((cost_cand - cost_base) / cost_base) * 100.0
        if cost_increase_pct > config.cost.max_increase_percent:
            failures.append(
                f"Cost per 100 requests increased by {cost_increase_pct:+.1f}%, exceeding max increase "
                f"{config.cost.max_increase_percent:.1f}%"
            )

    # 5. Language-specific breakdown checks
    for lang, lang_threshold in config.language_subsets.items():
        base_lang = report.baseline_summary.language_breakdown.get(lang)
        cand_lang = report.candidate_summary.language_breakdown.get(lang)

        if cand_lang is not None:
            if enforce_absolute and cand_lang.accuracy_percent < lang_threshold.min_accuracy:
                failures.append(
                    f"Language '{lang}' accuracy {cand_lang.accuracy_percent:.1f}% is below required "
                    f"{lang_threshold.min_accuracy:.1f}%"
                )
            if base_lang is not None:
                lang_drop = base_lang.accuracy_percent - cand_lang.accuracy_percent
                if lang_drop > lang_threshold.max_drop_percent:
                    failures.append(
                        f"Language '{lang}' accuracy dropped by {lang_drop:.1f}%, exceeding max drop "
                        f"{lang_threshold.max_drop_percent:.1f}%"
                    )

    passed = len(failures) == 0
    return (passed, failures)


def run_ci_gate(
    db: Session,
    baseline_llm: LLMProtocol,
    candidate_llm: LLMProtocol,
    max_drop_allowed: float = 2.0,
    gate_config_path: str | Path | None = None,
    enforce_absolute: bool | None = None,
    out: TextIO = sys.stdout,
) -> int:
    """
    Run CI gate evaluation with multi-dimensional criteria from YAML config.
    Returns:
        0 if candidate passes all quality & regression thresholds.
        1 if candidate fails any threshold.
    """
    config = load_gate_config(gate_config_path)
    # If explicit max_drop_allowed override provided
    if max_drop_allowed != 2.0:
        config.overall_accuracy.max_drop_percent = max_drop_allowed

    engine = RegressionEngine(db=db)
    cases = load_golden_cases()

    report: RegressionReport = engine.compare(
        baseline_llm=baseline_llm,
        candidate_llm=candidate_llm,
        cases=cases,
        baseline_version="v1",
        candidate_version="v2",
        max_allowed_drop_percent=config.overall_accuracy.max_drop_percent,
    )

    passed, failure_reasons = evaluate_regression_gate(report, config, enforce_absolute=enforce_absolute)

    out.write("\n")
    out.write("  ===============================================================\n")
    out.write(f"  [GATE] PROOFLINE CI EVALUATION GATE ({config.gate_name})\n")
    out.write("  ===============================================================\n")
    out.write(f"  Baseline Accuracy   : {report.baseline_summary.overall_accuracy:.1f}%\n")
    out.write(f"  Candidate Accuracy  : {report.candidate_summary.overall_accuracy:.1f}%\n")
    out.write(f"  Accuracy Delta      : {report.accuracy_delta:+.1f}%\n")
    out.write(f"  Guard Alignment     : {report.candidate_summary.guard_alignment:.1f}%\n")
    out.write(f"  P95 Latency         : {report.candidate_summary.p95_latency_ms:.1f} ms ({report.p95_latency_delta_ms:+.1f} ms)\n")
    out.write(f"  Cost / 100 req      : ${report.candidate_summary.cost_per_100_usd:.4f}\n")
    out.write(f"  Regressions Count   : {len(report.what_got_worse)}\n")
    out.write(f"  Improvements Count  : {len(report.what_got_better)}\n")
    out.write("  ---------------------------------------------------------------\n")

    if report.what_got_worse:
        out.write("  [WARNING] DETECTED REGRESSIONS ('WHAT GOT WORSE'):\n")
        for item in report.what_got_worse[:5]:
            out.write(f"     - [{item.case_id}] {item.ticket_text[:50]}...\n")
            for r in item.failure_reasons:
                out.write(f"       Reason: {r}\n")
        out.write("  ---------------------------------------------------------------\n")

    if not passed:
        out.write("  [FAIL] CI GATE FAILED -- PRODUCTION BLOCKED!\n")
        for r in failure_reasons:
            out.write(f"     * {r}\n")
        out.write("  ===============================================================\n\n")
        return 1

    out.write("  [PASS] CI GATE PASSED: Release candidate meets all enterprise reliability thresholds!\n")
    out.write("     Safe to proceed with deployment / PR merge.\n")
    out.write("  ===============================================================\n\n")
    return 0
