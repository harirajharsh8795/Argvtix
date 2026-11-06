"""
Argvtix Regression Gate CLI.
Evaluates candidate benchmark results against a committed baseline.
Used in CI and pre-deployment pipelines to block breaking changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from argvtix.regression.comparator import GateVerdict, evaluate_regression_gate


def run_gate(
    baseline_path: Path,
    candidate_path: Path,
    output_path: Path | None = None,
    fail_on_review: bool = False,
) -> int:
    if not baseline_path.exists():
        print(f"[GATE ERROR] Baseline file not found: {baseline_path}")
        return 1
    if not candidate_path.exists():
        print(f"[GATE ERROR] Candidate file not found: {candidate_path}")
        return 1

    with open(baseline_path, encoding="utf-8") as f:
        baseline_data: dict[str, Any] = json.load(f)
    with open(candidate_path, encoding="utf-8") as f:
        candidate_data: dict[str, Any] = json.load(f)

    report = evaluate_regression_gate(baseline_data, candidate_data)

    print("\n" + "=" * 60)
    print(f"ARGVTIX REGRESSION GATE RESULT: {report.verdict.value}")
    print("=" * 60)
    print(f"Summary: {report.summary}")

    if report.failed_checks:
        print("\n[CRITICAL REGRESSIONS]")
        for c in report.failed_checks:
            print(f"  ❌ {c.check_name}: {c.message}")

    if report.review_checks:
        print("\n[INFRASTRUCTURE REVIEWS]")
        for c in report.review_checks:
            print(f"  ⚠️  {c.check_name}: {c.message}")

    if report.passed_checks:
        print("\n[PASSED GATES]")
        for c in report.passed_checks:
            print(
                f"  ✅ {c.check_name}: baseline={c.baseline_value} -> candidate={c.candidate_value}"
            )
    print("=" * 60 + "\n")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"[GATE] Saved report to {output_path}")

    if report.verdict == GateVerdict.FAIL:
        return 1
    if report.verdict == GateVerdict.REVIEW and fail_on_review:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Argvtix Regression Gate Evaluator")
    parser.add_argument("--baseline", type=Path, required=True, help="Path to golden baseline JSON")
    parser.add_argument("--candidate", type=Path, required=True, help="Path to candidate run JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/verification/gate_result.json"),
        help="Path to write verdict report JSON",
    )
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="Treat REVIEW warnings (latency/cost) as blocking errors",
    )
    args = parser.parse_args()

    exit_code = run_gate(
        baseline_path=args.baseline,
        candidate_path=args.candidate,
        output_path=args.output,
        fail_on_review=args.fail_on_review,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
