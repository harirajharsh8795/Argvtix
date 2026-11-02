"""
Replay CLI Runner — Command-line interface to replay traces and run golden benchmarks.

Usage:
    python -m argvtix.replay.runner --trace tr-abc123
    python -m argvtix.replay.runner --suite
    python -m argvtix.replay.runner --case gold_ref_001
    python -m argvtix.replay.runner --workflow refund
"""

from __future__ import annotations

import argparse
import sys

from argvtix.db.session import SessionLocal, init_db
from argvtix.replay.engine import ReplayEngine
from argvtix.replay.golden import filter_golden_cases, get_golden_case, load_golden_cases
from argvtix.target_app.llm import MockLLM


def _divider(char: str = "-", width: int = 65) -> str:
    return char * width


def main() -> None:
    parser = argparse.ArgumentParser(description="ARGVTIX Replay & Benchmark CLI")
    parser.add_argument("--trace", help="Trace ID to replay from database")
    parser.add_argument(
        "--suite", action="store_true", help="Run full 50-case golden benchmark suite"
    )
    parser.add_argument("--case", help="Specific golden case ID to run (e.g. gold_ref_001)")
    parser.add_argument(
        "--workflow",
        choices=["refund", "cancel", "balance", "inventory", "subscription", "general"],
        help="Filter golden cases by workflow",
    )
    parser.add_argument(
        "--mock", action="store_true", default=True, help="Use deterministic MockLLM (default)"
    )
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    llm = MockLLM() if args.mock else None
    engine = ReplayEngine(db=db, default_llm=llm)

    print()
    print("  +-------------------------------------------------------------+")
    print("  |            ARGVTIX Replay & Golden Benchmark Runner            |")
    print("  +-------------------------------------------------------------+")

    try:
        if args.trace:
            print(f"\n  Replaying trace: {args.trace}")
            try:
                comp = engine.replay_trace(trace_id=args.trace)
                print(_divider("="))
                print(f"  ORIGINAL STATUS : {comp.original_status.upper()}")
                print(f"  REPLAYED STATUS : {comp.replayed_status.upper()}")
                print(f"  ORIGINAL GUARD  : {comp.original_guard_decision.upper()}")
                print(f"  REPLAYED GUARD  : {comp.replayed_guard_decision.upper()}")
                print(
                    f"  GUARD MATCH     : {'YES' if comp.guard_decisions_match else 'NO (DRIFT DETECTED)'}"
                )
                print(f"  LATENCY DELTA   : {comp.latency_delta_ms:+.1f} ms")
                print(f"  TOKENS DELTA    : {comp.tokens_delta:+d} tokens")
                print(_divider("="))
            except ValueError as e:
                print(f"  Error: {e}")
                sys.exit(1)

        elif args.case:
            case = get_golden_case(args.case)
            if not case:
                print(f"  Golden case not found: {args.case}")
                sys.exit(1)
            print(f"\n  Running Golden Case: {case.id} [{case.workflow.upper()}]")
            res = engine.replay_case(case)
            print(_divider("="))
            print(f"  TICKET    : {res.ticket_text}")
            print(
                f"  INTENT    : {res.actual_intent} (Expected: {res.expected_intent}) -> {'MATCH' if res.intent_match else 'MISMATCH'}"
            )
            print(
                f"  GUARD     : {res.actual_guard.upper()} (Expected: {res.expected_guard.upper()}) -> {'MATCH' if res.guard_match else 'MISMATCH'}"
            )
            print(f"  VERDICT   : {'PASSED' if res.is_passed else 'FAILED'}")
            print(f"  LATENCY   : {res.latency_ms:.1f} ms")
            if res.failure_reasons:
                print("  REASONS   :")
                for r in res.failure_reasons:
                    print(f"    - {r}")
            print(_divider("="))

        elif args.suite or args.workflow:
            cases = (
                filter_golden_cases(workflow=args.workflow)
                if args.workflow
                else load_golden_cases()
            )
            total_count = len(cases)
            wf_label = f"[{args.workflow.upper()}]" if args.workflow else "[ALL WORKFLOWS]"
            print(f"\n  Running {total_count} Golden Benchmark Cases {wf_label}...\n")
            bench = engine.run_suite(cases=cases)

            print(
                f"  {'Case ID':<14} | {'Workflow':<10} | {'Intent':<7} | {'Guard':<7} | {'Result':<6} | {'Latency':<8}"
            )
            print(_divider("-"))
            for r in bench.case_results:
                int_str = "OK" if r.intent_match else "FAIL"
                grd_str = "OK" if r.guard_match else "FAIL"
                res_str = "PASS" if r.is_passed else "FAIL"
                lat_str = f"{r.latency_ms:.0f}ms"
                print(
                    f"  {r.case_id:<14} | {r.workflow:<10} | {int_str:<7} | {grd_str:<7} | {res_str:<6} | {lat_str:<8}"
                )

            print(_divider("="))
            print(f"  TOTAL CASES     : {bench.total_cases}")
            print(f"  PASSED CASES    : {bench.passed_cases}")
            print(f"  FAILED CASES    : {bench.failed_cases}")
            print(f"  ACCURACY        : {bench.accuracy_percent:.1f}%")
            print(f"  INTENT ACCURACY : {bench.intent_accuracy_percent:.1f}%")
            print(f"  GUARD ALIGNMENT : {bench.guard_accuracy_percent:.1f}%")
            print(_divider("="))

        else:
            parser.print_help()

    finally:
        db.close()


if __name__ == "__main__":
    main()
