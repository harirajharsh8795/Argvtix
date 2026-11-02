"""
Regression Engine — Detects performance degradation between AI agent versions.

Compares:
- Baseline (Config A / Prompt v1 / Model A)
- Candidate (Config B / Prompt v2 / Model B)

Identifies:
- 'What got worse': Cases that passed in Baseline but fail in Candidate (REGRESSIONS).
- 'What got better': Cases that failed in Baseline but pass in Candidate (IMPROVEMENTS).
- Metric deltas: Accuracy delta, latency delta, token delta, language drop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from argvtix.evals.metrics import EvaluationSummary, compute_evaluation_summary
from argvtix.replay.engine import CaseReplayResult, ReplayEngine
from argvtix.replay.golden import GoldenCase, load_golden_cases
from argvtix.target_app.llm import LLMProtocol


@dataclass
class RegressionItem:
    """A specific case where candidate performed worse than baseline."""
    case_id: str
    workflow: str
    ticket_text: str
    baseline_result: str   # 'PASS'
    candidate_result: str  # 'FAIL'
    failure_reasons: list[str]


@dataclass
class ImprovementItem:
    """A specific case where candidate performed better than baseline."""
    case_id: str
    workflow: str
    ticket_text: str
    baseline_result: str   # 'FAIL'
    candidate_result: str  # 'PASS'


@dataclass
class RegressionReport:
    """Comprehensive comparison between baseline and candidate configurations."""
    baseline_version: str
    candidate_version: str
    baseline_summary: EvaluationSummary
    candidate_summary: EvaluationSummary
    accuracy_delta: float
    intent_delta: float
    guard_delta: float
    p95_latency_delta_ms: float
    what_got_worse: list[RegressionItem] = field(default_factory=list)
    what_got_better: list[ImprovementItem] = field(default_factory=list)
    has_critical_regression: bool = False
    verdict: str = "PASSED"  # 'PASSED' | 'FAILED_REGRESSION'

    @property
    def cost_delta_usd(self) -> float:
        return round(self.candidate_summary.total_cost_usd - self.baseline_summary.total_cost_usd, 5)


class RegressionEngine:
    """
    Coordinates baseline vs candidate evaluations and computes regression reports.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def evaluate_config(
        self,
        cases: list[GoldenCase],
        llm: LLMProtocol,
    ) -> tuple[EvaluationSummary, dict[str, CaseReplayResult]]:
        """Run golden cases using a specific LLM/prompt and return summary + map."""
        replayer = ReplayEngine(db=self.db, default_llm=llm)
        case_map: dict[str, CaseReplayResult] = {}
        eval_items: list[dict[str, Any]] = []

        for c in cases:
            res = replayer.replay_case(c, llm=llm)
            case_map[c.id] = res

            eval_items.append({
                "workflow": c.workflow,
                "ticket_text": c.ticket_text,
                "expected_intent": c.expected_intent,
                "actual_intent": res.actual_intent,
                "expected_guard": c.expected_guard_decision,
                "actual_guard": res.actual_guard,
                "expected_tool": c.expected_tool,
                "actual_tool": res.actual_intent if res.is_passed else None,
                "latency_ms": res.latency_ms,
                "cost_usd": 0.0001,
            })

        summary = compute_evaluation_summary(eval_items)
        return summary, case_map

    def compare(
        self,
        baseline_llm: LLMProtocol,
        candidate_llm: LLMProtocol,
        cases: list[GoldenCase] | None = None,
        baseline_version: str = "v1",
        candidate_version: str = "v2",
        max_allowed_drop_percent: float = 0.0,
    ) -> RegressionReport:
        """
        Compare baseline vs candidate on golden cases.
        If accuracy drops by more than max_allowed_drop_percent, flags as FAILED_REGRESSION.
        """
        test_cases = cases or load_golden_cases()

        base_summary, base_map = self.evaluate_config(test_cases, baseline_llm)
        cand_summary, cand_map = self.evaluate_config(test_cases, candidate_llm)

        what_got_worse: list[RegressionItem] = []
        what_got_better: list[ImprovementItem] = []

        for c in test_cases:
            b_res = base_map.get(c.id)
            c_res = cand_map.get(c.id)
            if not b_res or not c_res:
                continue

            # Case passed in baseline, but failed in candidate -> REGRESSION
            if b_res.is_passed and not c_res.is_passed:
                what_got_worse.append(RegressionItem(
                    case_id=c.id,
                    workflow=c.workflow,
                    ticket_text=c.ticket_text,
                    baseline_result="PASS",
                    candidate_result="FAIL",
                    failure_reasons=c_res.failure_reasons,
                ))

            # Case failed in baseline, but passed in candidate -> IMPROVEMENT
            elif not b_res.is_passed and c_res.is_passed:
                what_got_better.append(ImprovementItem(
                    case_id=c.id,
                    workflow=c.workflow,
                    ticket_text=c.ticket_text,
                    baseline_result="FAIL",
                    candidate_result="PASS",
                ))

        acc_delta = round(cand_summary.overall_accuracy - base_summary.overall_accuracy, 1)
        int_delta = round(cand_summary.intent_accuracy - base_summary.intent_accuracy, 1)
        grd_delta = round(cand_summary.guard_alignment - base_summary.guard_alignment, 1)
        lat_delta = round(cand_summary.p95_latency_ms - base_summary.p95_latency_ms, 1)

        # Critical regression triggered if any case regressed or overall drop exceeds threshold
        has_critical = (len(what_got_worse) > 0) or (acc_delta < -abs(max_allowed_drop_percent))
        verdict = "FAILED_REGRESSION" if has_critical else "PASSED"

        return RegressionReport(
            baseline_version=baseline_version,
            candidate_version=candidate_version,
            baseline_summary=base_summary,
            candidate_summary=cand_summary,
            accuracy_delta=acc_delta,
            intent_delta=int_delta,
            guard_delta=grd_delta,
            p95_latency_delta_ms=lat_delta,
            what_got_worse=what_got_worse,
            what_got_better=what_got_better,
            has_critical_regression=has_critical,
            verdict=verdict,
        )
