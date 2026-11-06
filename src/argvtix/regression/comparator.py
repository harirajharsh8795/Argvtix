"""
Argvtix Regression Gate Comparator.
Evaluates candidate benchmark/eval metrics against a golden baseline.
Distinguishes between code/accuracy regressions (FAIL) and infrastructure variance (REVIEW).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GateVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


@dataclass
class CheckResult:
    check_name: str
    verdict: GateVerdict
    baseline_value: float | str | None
    candidate_value: float | str | None
    delta: float | str | None
    threshold: float | str | None
    message: str


@dataclass
class GateReport:
    verdict: GateVerdict
    overall_pass: bool
    summary: str
    reasons: list[str] = field(default_factory=list)
    failed_checks: list[CheckResult] = field(default_factory=list)
    review_checks: list[CheckResult] = field(default_factory=list)
    passed_checks: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "overall_pass": self.overall_pass,
            "summary": self.summary,
            "reasons": self.reasons,
            "failed_checks": [asdict(c) for c in self.failed_checks],
            "review_checks": [asdict(c) for c in self.review_checks],
            "passed_checks": [asdict(c) for c in self.passed_checks],
        }


class RegressionComparator:
    """Evaluates candidate performance deltas against configured safety and accuracy gates."""

    def __init__(
        self,
        max_accuracy_drop_pct: float = 2.0,
        max_state_grounding_recall_drop_pct: float = 3.0,
        max_guard_fpr_increase_pct: float = 2.0,
        max_hindi_accuracy_drop_pct: float = 3.0,
        max_hinglish_accuracy_drop_pct: float = 3.0,
        max_latency_p95_spike_pct: float = 50.0,
        max_cost_surge_pct: float = 30.0,
    ) -> None:
        self.max_accuracy_drop_pct = max_accuracy_drop_pct
        self.max_state_grounding_recall_drop_pct = max_state_grounding_recall_drop_pct
        self.max_guard_fpr_increase_pct = max_guard_fpr_increase_pct
        self.max_hindi_accuracy_drop_pct = max_hindi_accuracy_drop_pct
        self.max_hinglish_accuracy_drop_pct = max_hinglish_accuracy_drop_pct
        self.max_latency_p95_spike_pct = max_latency_p95_spike_pct
        self.max_cost_surge_pct = max_cost_surge_pct

    def compare(self, baseline: dict[str, Any], candidate: dict[str, Any]) -> GateReport:
        failed_checks: list[CheckResult] = []
        review_checks: list[CheckResult] = []
        passed_checks: list[CheckResult] = []
        reasons: list[str] = []

        # 1. Overall Accuracy Check (FAIL if drop > threshold)
        b_acc = float(baseline.get("overall_accuracy_pct", baseline.get("accuracy_percent", 100.0)))
        c_acc = float(
            candidate.get("overall_accuracy_pct", candidate.get("accuracy_percent", 100.0))
        )
        acc_delta = round(c_acc - b_acc, 2)
        if acc_delta < -self.max_accuracy_drop_pct:
            chk = CheckResult(
                check_name="overall_accuracy",
                verdict=GateVerdict.FAIL,
                baseline_value=b_acc,
                candidate_value=c_acc,
                delta=acc_delta,
                threshold=-self.max_accuracy_drop_pct,
                message=f"Overall accuracy dropped by {abs(acc_delta)}% (allowed max {self.max_accuracy_drop_pct}%).",
            )
            failed_checks.append(chk)
            reasons.append(chk.message)
        else:
            passed_checks.append(
                CheckResult(
                    "overall_accuracy",
                    GateVerdict.PASS,
                    b_acc,
                    c_acc,
                    acc_delta,
                    -self.max_accuracy_drop_pct,
                    "OK",
                )
            )

        # 2. State Grounding Recall Check (FAIL if drop > threshold)
        b_sg = float(baseline.get("state_grounding_recall_pct", 100.0))
        c_sg = float(candidate.get("state_grounding_recall_pct", 100.0))
        sg_delta = round(c_sg - b_sg, 2)
        if sg_delta < -self.max_state_grounding_recall_drop_pct:
            chk = CheckResult(
                check_name="state_grounding_recall",
                verdict=GateVerdict.FAIL,
                baseline_value=b_sg,
                candidate_value=c_sg,
                delta=sg_delta,
                threshold=-self.max_state_grounding_recall_drop_pct,
                message=f"State grounding recall dropped by {abs(sg_delta)}% (allowed max {self.max_state_grounding_recall_drop_pct}%).",
            )
            failed_checks.append(chk)
            reasons.append(chk.message)
        else:
            passed_checks.append(
                CheckResult(
                    "state_grounding_recall",
                    GateVerdict.PASS,
                    b_sg,
                    c_sg,
                    sg_delta,
                    -self.max_state_grounding_recall_drop_pct,
                    "OK",
                )
            )

        # 3. Guard Policy Safety Check (FAIL if guard weakened or bypassed)
        b_bypass = int(baseline.get("guard_bypasses_count", 0))
        c_bypass = int(candidate.get("guard_bypasses_count", 0))
        if c_bypass > b_bypass:
            chk = CheckResult(
                check_name="guard_weakened",
                verdict=GateVerdict.FAIL,
                baseline_value=b_bypass,
                candidate_value=c_bypass,
                delta=c_bypass - b_bypass,
                threshold=0,
                message=f"Guard policy safety weakened: candidate allowed {c_bypass} policy violations (baseline was {b_bypass}).",
            )
            failed_checks.append(chk)
            reasons.append(chk.message)
        else:
            passed_checks.append(
                CheckResult("guard_weakened", GateVerdict.PASS, b_bypass, c_bypass, 0, 0, "OK")
            )

        # 4. Multilingual: Hindi Accuracy Check (FAIL if drop > threshold)
        if "hindi_accuracy_pct" in baseline and "hindi_accuracy_pct" in candidate:
            b_hi = float(baseline["hindi_accuracy_pct"])
            c_hi = float(candidate["hindi_accuracy_pct"])
            hi_delta = round(c_hi - b_hi, 2)
            if hi_delta < -self.max_hindi_accuracy_drop_pct:
                chk = CheckResult(
                    check_name="hindi_accuracy",
                    verdict=GateVerdict.FAIL,
                    baseline_value=b_hi,
                    candidate_value=c_hi,
                    delta=hi_delta,
                    threshold=-self.max_hindi_accuracy_drop_pct,
                    message=f"Hindi language accuracy dropped by {abs(hi_delta)}% (allowed max {self.max_hindi_accuracy_drop_pct}%).",
                )
                failed_checks.append(chk)
                reasons.append(chk.message)
            else:
                passed_checks.append(
                    CheckResult(
                        "hindi_accuracy",
                        GateVerdict.PASS,
                        b_hi,
                        c_hi,
                        hi_delta,
                        -self.max_hindi_accuracy_drop_pct,
                        "OK",
                    )
                )

        # 5. Multilingual: Hinglish Accuracy Check (FAIL if drop > threshold)
        if "hinglish_accuracy_pct" in baseline and "hinglish_accuracy_pct" in candidate:
            b_hin = float(baseline["hinglish_accuracy_pct"])
            c_hin = float(candidate["hinglish_accuracy_pct"])
            hin_delta = round(c_hin - b_hin, 2)
            if hin_delta < -self.max_hinglish_accuracy_drop_pct:
                chk = CheckResult(
                    check_name="hinglish_accuracy",
                    verdict=GateVerdict.FAIL,
                    baseline_value=b_hin,
                    candidate_value=c_hin,
                    delta=hin_delta,
                    threshold=-self.max_hinglish_accuracy_drop_pct,
                    message=f"Hinglish language accuracy dropped by {abs(hin_delta)}% (allowed max {self.max_hinglish_accuracy_drop_pct}%).",
                )
                failed_checks.append(chk)
                reasons.append(chk.message)
            else:
                passed_checks.append(
                    CheckResult(
                        "hinglish_accuracy",
                        GateVerdict.PASS,
                        b_hin,
                        c_hin,
                        hin_delta,
                        -self.max_hinglish_accuracy_drop_pct,
                        "OK",
                    )
                )

        # 6. Infrastructure: Latency Spike Check (REVIEW if spike > threshold)
        b_p95 = float(baseline.get("p95_latency_ms", 100.0))
        c_p95 = float(candidate.get("p95_latency_ms", 100.0))
        if b_p95 > 0:
            lat_pct = round(((c_p95 - b_p95) / b_p95) * 100.0, 2)
            if lat_pct > self.max_latency_p95_spike_pct:
                chk = CheckResult(
                    check_name="latency_spike",
                    verdict=GateVerdict.REVIEW,
                    baseline_value=b_p95,
                    candidate_value=c_p95,
                    delta=f"+{lat_pct}%",
                    threshold=f"+{self.max_latency_p95_spike_pct}%",
                    message=f"Infrastructure review: p95 latency surged by {lat_pct}% from {b_p95}ms to {c_p95}ms.",
                )
                review_checks.append(chk)
                reasons.append(chk.message)
            else:
                passed_checks.append(
                    CheckResult(
                        "latency_spike",
                        GateVerdict.PASS,
                        b_p95,
                        c_p95,
                        f"{lat_pct}%",
                        f"+{self.max_latency_p95_spike_pct}%",
                        "OK",
                    )
                )

        # 7. Infrastructure: Cost Surge Check (REVIEW if surge > threshold)
        b_cost = float(baseline.get("cost_usd_per_1k", 0.01))
        c_cost = float(candidate.get("cost_usd_per_1k", 0.01))
        if b_cost > 0:
            cost_pct = round(((c_cost - b_cost) / b_cost) * 100.0, 2)
            if cost_pct > self.max_cost_surge_pct:
                chk = CheckResult(
                    check_name="cost_surge",
                    verdict=GateVerdict.REVIEW,
                    baseline_value=b_cost,
                    candidate_value=c_cost,
                    delta=f"+{cost_pct}%",
                    threshold=f"+{self.max_cost_surge_pct}%",
                    message=f"Cost surge review: per-1k cost rose by {cost_pct}% from ${b_cost} to ${c_cost}.",
                )
                review_checks.append(chk)
                reasons.append(chk.message)
            else:
                passed_checks.append(
                    CheckResult(
                        "cost_surge",
                        GateVerdict.PASS,
                        b_cost,
                        c_cost,
                        f"{cost_pct}%",
                        f"+{self.max_cost_surge_pct}%",
                        "OK",
                    )
                )

        # Determine overall verdict
        if failed_checks:
            overall_verdict = GateVerdict.FAIL
            overall_pass = False
            summary = f"REJECTED: {len(failed_checks)} critical regressions detected."
        elif review_checks:
            overall_verdict = GateVerdict.REVIEW
            overall_pass = True  # Does not block deployment, but flags for human review
            summary = f"NEEDS_REVIEW: {len(review_checks)} infrastructure metrics flagged for operator inspection."
        else:
            overall_verdict = GateVerdict.PASS
            overall_pass = True
            summary = "PASSED: All accuracy, safety, and infrastructure gates satisfied."

        return GateReport(
            verdict=overall_verdict,
            overall_pass=overall_pass,
            summary=summary,
            reasons=reasons,
            failed_checks=failed_checks,
            review_checks=review_checks,
            passed_checks=passed_checks,
        )


def evaluate_regression_gate(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    rules: dict[str, Any] | None = None,
) -> GateReport:
    rules = rules or {}
    comparator = RegressionComparator(
        max_accuracy_drop_pct=rules.get("max_accuracy_drop_pct", 2.0),
        max_state_grounding_recall_drop_pct=rules.get("max_state_grounding_recall_drop_pct", 3.0),
        max_guard_fpr_increase_pct=rules.get("max_guard_fpr_increase_pct", 2.0),
        max_hindi_accuracy_drop_pct=rules.get("max_hindi_accuracy_drop_pct", 3.0),
        max_hinglish_accuracy_drop_pct=rules.get("max_hinglish_accuracy_drop_pct", 3.0),
        max_latency_p95_spike_pct=rules.get("max_latency_p95_spike_pct", 50.0),
        max_cost_surge_pct=rules.get("max_cost_surge_pct", 30.0),
    )
    return comparator.compare(baseline, candidate)
