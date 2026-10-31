"""
pass^k Reliability Runner Module.

Implements rigorous multi-trial reliability evaluation for non-deterministic AI agents:
1. pass@1: Average single-run accuracy.
2. pass@k: Standard HumanEval metric — probability of at least one success in k attempts.
3. pass^k (pass-hat-k): Strict production reliability — probability that all k attempts succeed in a row.
4. flake_rate: Percentage of test cases that pass intermittently (0 < successes < k).
5. Reliability Score: Production readiness index (0 - 100).
"""

from __future__ import annotations

import math
from typing import Any, Callable

from pydantic import BaseModel, Field


def estimate_pass_at_k(num_samples: int, num_correct: int, k: int) -> float:
    """
    Computes unbiased pass@k estimator from Chen et al. (Codex / HumanEval):
    pass@k = 1 - C(n - c, k) / C(n, k)
    """
    if num_samples - num_correct < k:
        return 1.0
    if num_correct == 0:
        return 0.0
    if k > num_samples:
        return 1.0 if num_correct > 0 else 0.0

    # Calculate combination ratio using logarithms for numerical stability
    # prod_{i=1}^k (n - c - k + i) / (n - k + i)
    log_comb = 0.0
    for i in range(1, k + 1):
        log_comb += math.log(num_samples - num_correct - k + i) - math.log(num_samples - k + i)

    return 1.0 - math.exp(log_comb)


class PassKCaseResult(BaseModel):
    """Execution results for a single test case across k trials."""

    case_id: str
    total_trials: int
    successful_trials: int
    is_flaky: bool
    is_all_passed: bool
    is_all_failed: bool
    trial_outputs: list[dict[str, Any]] = Field(default_factory=list)


class PassKReport(BaseModel):
    """Consolidated report across all evaluated cases."""

    k: int
    total_cases: int
    pass_at_1: float
    pass_at_k: float
    pass_hat_k: float
    flake_rate: float
    flaky_case_ids: list[str] = Field(default_factory=list)
    perfect_case_ids: list[str] = Field(default_factory=list)
    failed_case_ids: list[str] = Field(default_factory=list)
    case_details: list[PassKCaseResult] = Field(default_factory=list)
    reliability_index: float = Field(
        ...,
        description="Composite score (0-100) emphasizing all-trial consistency and zero flakes",
    )


class PassKRunner:
    """
    Executes multiple trials per scenario to measure consistency, flake rate,
    and pass^k reliability.
    """

    def __init__(self, k: int = 5) -> None:
        if k < 1:
            raise ValueError("k must be at least 1")
        self.k = k

    def evaluate_case(
        self,
        case_id: str,
        eval_fn: Callable[[], bool | tuple[bool, Any]],
        k: int | None = None,
    ) -> PassKCaseResult:
        """Runs k trials for a single case and records success/fail/flake."""
        trials_count = k or self.k
        successes = 0
        outputs: list[dict[str, Any]] = []

        for trial_idx in range(trials_count):
            res = eval_fn()
            success = False
            details = None

            if isinstance(res, tuple):
                success, details = res
            elif isinstance(res, bool):
                success = res

            if success:
                successes += 1

            outputs.append(
                {
                    "trial": trial_idx + 1,
                    "passed": bool(success),
                    "details": details,
                }
            )

        is_flaky = 0 < successes < trials_count
        is_all_passed = successes == trials_count
        is_all_failed = successes == 0

        return PassKCaseResult(
            case_id=case_id,
            total_trials=trials_count,
            successful_trials=successes,
            is_flaky=is_flaky,
            is_all_passed=is_all_passed,
            is_all_failed=is_all_failed,
            trial_outputs=outputs,
        )

    def run(
        self,
        cases: list[tuple[str, Callable[[], bool | tuple[bool, Any]]]],
        k: int | None = None,
    ) -> PassKReport:
        """
        Runs the full pass^k evaluation across a list of (case_id, eval_fn) tuples.
        """
        eval_k = k or self.k
        if not cases:
            return PassKReport(
                k=eval_k,
                total_cases=0,
                pass_at_1=100.0,
                pass_at_k=100.0,
                pass_hat_k=100.0,
                flake_rate=0.0,
                reliability_index=100.0,
            )

        case_results: list[PassKCaseResult] = []
        total_trials_all = 0
        total_successes_all = 0
        all_passed_count = 0
        flaky_count = 0
        at_least_one_pass_count = 0

        flaky_ids: list[str] = []
        perfect_ids: list[str] = []
        failed_ids: list[str] = []

        for case_id, fn in cases:
            res = self.evaluate_case(case_id, fn, k=eval_k)
            case_results.append(res)

            total_trials_all += res.total_trials
            total_successes_all += res.successful_trials

            if res.is_all_passed:
                all_passed_count += 1
                perfect_ids.append(case_id)
            elif res.is_all_failed:
                failed_ids.append(case_id)

            if res.is_flaky:
                flaky_count += 1
                flaky_ids.append(case_id)

            if res.successful_trials >= 1:
                at_least_one_pass_count += 1

        total_cases = len(cases)

        # 1. pass@1 = average single run accuracy
        pass_at_1 = (total_successes_all / total_trials_all * 100.0) if total_trials_all > 0 else 0.0

        # 2. pass@k = proportion where at least 1 attempt succeeded
        pass_at_k = (at_least_one_pass_count / total_cases * 100.0) if total_cases > 0 else 0.0

        # 3. pass^k = proportion where ALL k attempts succeeded in a row
        pass_hat_k = (all_passed_count / total_cases * 100.0) if total_cases > 0 else 0.0

        # 4. flake_rate = proportion that exhibited inconsistency
        flake_rate = (flaky_count / total_cases * 100.0) if total_cases > 0 else 0.0

        # 5. Composite reliability index:
        # Heavily rewards pass^k and penalizes flakiness
        reliability_index = max(0.0, min(100.0, (pass_hat_k * 0.8) + (pass_at_1 * 0.2) - (flake_rate * 0.5)))

        return PassKReport(
            k=eval_k,
            total_cases=total_cases,
            pass_at_1=round(pass_at_1, 2),
            pass_at_k=round(pass_at_k, 2),
            pass_hat_k=round(pass_hat_k, 2),
            flake_rate=round(flake_rate, 2),
            flaky_case_ids=flaky_ids,
            perfect_case_ids=perfect_ids,
            failed_case_ids=failed_ids,
            case_details=case_results,
            reliability_index=round(reliability_index, 2),
        )
