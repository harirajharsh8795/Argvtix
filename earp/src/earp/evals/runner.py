"""
Evaluation & Regression CLI Runner.

Usage:
    python -m earp.evals.runner --summary
    python -m earp.evals.runner --workflow refund
    python -m earp.evals.runner --gate --threshold 5.0
"""
from __future__ import annotations

import argparse
import sys

from earp.db.session import SessionLocal, init_db
from earp.evals.ci_gate import run_ci_gate
from earp.evals.regression import RegressionEngine
from earp.replay.golden import filter_golden_cases, load_golden_cases
from earp.target_app.llm import MockLLM


def _divider(char: str = "-", width: int = 65) -> str:
    return char * width


def display_eval_summary(summary, title: str = "EVALUATION SUMMARY") -> None:
    print()
    print(_divider("="))
    print(f"  [METRICS] {title}")
    print(_divider("-"))
    print(f"  Total Evaluations   : {summary.total_evals}")
    print(f"  Overall Accuracy    : {summary.overall_accuracy:.1f}%")
    print(f"  Intent Accuracy     : {summary.intent_accuracy:.1f}%")
    print(f"  Guard Alignment     : {summary.guard_alignment:.1f}%")
    print(f"  Tool Accuracy       : {summary.tool_accuracy:.1f}%")
    print(f"  P50 Latency         : {summary.p50_latency_ms:.1f} ms")
    print(f"  P90 Latency         : {summary.p90_latency_ms:.1f} ms")
    print(f"  P95 Latency         : {summary.p95_latency_ms:.1f} ms")
    print(f"  Total Cost          : ${summary.total_cost_usd:.5f}")
    print(f"  Cost / 100 Reqs     : ${summary.cost_per_100_usd:.4f}")
    print(_divider("-"))
    print("  LANGUAGE BREAKDOWN:")
    for lang, metrics in summary.language_breakdown.items():
        lang_name = "English" if lang == "en" else ("Hindi" if lang == "hi" else "Hinglish")
        print(f"    - {lang_name:<10} ({metrics.total:>2} cases): {metrics.accuracy_percent:>5.1f}% [{metrics.passed}/{metrics.total}]")
    print(_divider("-"))
    print("  WORKFLOW ACCURACY:")
    for wf, acc in summary.workflow_breakdown.items():
        print(f"    - {wf:<14}: {acc:.1f}%")
    print(_divider("="))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="EARP Evaluation & Regression Runner")
    parser.add_argument("--summary", action="store_true", help="Run golden evaluation and display summary metrics")
    parser.add_argument("--workflow", choices=["refund", "cancel", "balance", "inventory", "subscription", "general"], help="Filter by workflow")
    parser.add_argument("--gate", action="store_true", help="Run automated CI regression gate")
    parser.add_argument("--threshold", type=float, default=5.0, help="Max allowed drop percent for CI gate (default: 5.0)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    llm = MockLLM()

    try:
        if args.gate:
            code = run_ci_gate(
                db=db,
                baseline_llm=llm,
                candidate_llm=llm,
                max_drop_allowed=args.threshold,
            )
            sys.exit(code)

        elif args.workflow:
            cases = filter_golden_cases(workflow=args.workflow)
            engine = RegressionEngine(db=db)
            summary, _ = engine.evaluate_config(cases, llm)
            display_eval_summary(summary, title=f"EVALUATION: {args.workflow.upper()} WORKFLOW")

        else:
            # Default: run full golden suite summary
            cases = load_golden_cases()
            engine = RegressionEngine(db=db)
            summary, _ = engine.evaluate_config(cases, llm)
            display_eval_summary(summary, title="GOLDEN SUITE EVALUATION (50 CASES)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
