"""
Multi-Model Benchmark Runner.

Runs the EARP golden evaluation suite against multiple LLM adapters
simultaneously and aggregates per-model accuracy, latency, and cost.

Usage:
    python -m earp.evals.benchmarks.runner --models gemini claude gpt4o-mini
    python -m earp.evals.benchmarks.runner --models gemini --workflow refund
    python -m earp.evals.benchmarks.runner --dry-run   # Mock only, no API calls
"""
from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

from earp.evals.benchmarks.adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    GPT4oAdapter,
    LiteLLMAdapter,
    MockAdapter,
    ModelAdapter,
    ModelResponse,
)
from earp.replay.golden import GoldenCase, filter_golden_cases, load_golden_cases


# ---------------------------------------------------------------------------
# Result schemas
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    """Result for a single golden case run against one model."""
    case_id: str
    model_id: str
    response_text: str
    expected_intent: str
    predicted_intent: str
    intent_match: bool
    latency_ms: float
    cost_usd: float
    error: str | None = None


@dataclass
class ModelBenchmarkResult:
    """Aggregated benchmark results for a single model."""
    model_id: str
    total_cases: int
    passed: int
    failed: int
    error_count: int
    accuracy_pct: float
    p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    total_cost_usd: float
    cost_per_100_usd: float
    case_results: list[CaseResult] = field(default_factory=list)

    @property
    def failed_pct(self) -> float:
        return 100.0 - self.accuracy_pct


@dataclass
class BenchmarkRunResult:
    """Full benchmark run comparing N models on M cases."""
    run_id: str
    timestamp: str
    total_models: int
    total_cases: int
    model_results: list[ModelBenchmarkResult] = field(default_factory=list)
    winner_accuracy: str = ""          # model_id with best accuracy
    winner_cost: str = ""             # model_id with lowest cost
    winner_latency: str = ""          # model_id with lowest p50 latency

    def ranked_by_accuracy(self) -> list[ModelBenchmarkResult]:
        return sorted(self.model_results, key=lambda r: r.accuracy_pct, reverse=True)

    def ranked_by_cost(self) -> list[ModelBenchmarkResult]:
        return sorted(self.model_results, key=lambda r: r.total_cost_usd)

    def ranked_by_latency(self) -> list[ModelBenchmarkResult]:
        return sorted(self.model_results, key=lambda r: r.p50_latency_ms)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a helpful customer-service AI agent for an e-commerce platform. "
    "Answer concisely and correctly. If a tool action is required, state it clearly."
)

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "refund":       ["refund", "money back", "reimburse"],
    "cancel":       ["cancel", "cancellation", "cancel order"],
    "balance":      ["balance", "wallet", "credit"],
    "inventory":    ["inventory", "stock", "available"],
    "subscription": ["subscription", "plan", "renew"],
    "general":      [],
}


def _extract_intent(text: str) -> str:
    low = text.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if intent == "general":
            continue
        if any(kw in low for kw in keywords):
            return intent
    return "general"


def _build_eval_prompt(case: GoldenCase) -> str:
    text = getattr(case, "ticket_text", None) or getattr(case, "input_text", "")
    return (
        f"Customer message: {text}\n\n"
        "Respond as the AI agent. Be concise and actionable."
    )


# ---------------------------------------------------------------------------
# Per-model evaluator
# ---------------------------------------------------------------------------

def _evaluate_model(
    adapter: ModelAdapter,
    cases: list[GoldenCase],
) -> ModelBenchmarkResult:
    """Run all golden cases against a single adapter."""
    results: list[CaseResult] = []
    latencies: list[float] = []

    for case in cases:
        cid = getattr(case, "id", None) or getattr(case, "case_id", "unknown")
        prompt = _build_eval_prompt(case)
        response: ModelResponse = adapter.generate(prompt, system_prompt=_SYSTEM_PROMPT)

        if response.error:
            results.append(CaseResult(
                case_id=cid,
                model_id=adapter.model_id,
                response_text="",
                expected_intent=case.workflow,
                predicted_intent="error",
                intent_match=False,
                latency_ms=0,
                cost_usd=0,
                error=response.error,
            ))
            continue

        predicted = _extract_intent(response.text)
        match = predicted == case.workflow or case.workflow == "general"

        results.append(CaseResult(
            case_id=cid,
            model_id=adapter.model_id,
            response_text=response.text,
            expected_intent=case.workflow,
            predicted_intent=predicted,
            intent_match=match,
            latency_ms=response.latency_ms,
            cost_usd=response.cost_usd,
        ))
        latencies.append(response.latency_ms)

    # Aggregate
    passed = sum(1 for r in results if r.intent_match)
    errors = sum(1 for r in results if r.error)
    total = len(results)
    accuracy = (passed / total * 100) if total else 0.0
    total_cost = sum(r.cost_usd for r in results)

    sorted_lat = sorted(latencies) if latencies else [0.0]

    def percentile(data: list[float], p: float) -> float:
        if not data:
            return 0.0
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]

    return ModelBenchmarkResult(
        model_id=adapter.model_id,
        total_cases=total,
        passed=passed,
        failed=total - passed - errors,
        error_count=errors,
        accuracy_pct=accuracy,
        p50_latency_ms=percentile(sorted_lat, 50),
        p90_latency_ms=percentile(sorted_lat, 90),
        p95_latency_ms=percentile(sorted_lat, 95),
        total_cost_usd=total_cost,
        cost_per_100_usd=(total_cost / total * 100) if total else 0.0,
        case_results=results,
    )


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------

class BenchmarkRunner:
    """
    Orchestrates parallel multi-model evaluation runs.

    Example:
        runner = BenchmarkRunner(adapters=[GeminiAdapter(), ClaudeAdapter()])
        result = runner.run(workflow="refund")
        print(result.ranked_by_accuracy())
    """

    def __init__(
        self,
        adapters: list[ModelAdapter] | None = None,
        max_workers: int = 4,
    ) -> None:
        self.adapters = adapters or [MockAdapter()]
        self.max_workers = max_workers

    def run(
        self,
        workflow: str | None = None,
        max_cases: int | None = None,
    ) -> BenchmarkRunResult:
        """
        Run benchmark across all adapters.

        Args:
            workflow: Filter golden cases by workflow name.
            max_cases: Cap number of cases (useful for quick smoke tests).
        """
        if workflow:
            cases = filter_golden_cases(workflow=workflow)
        else:
            cases = load_golden_cases()

        if max_cases:
            cases = cases[:max_cases]

        run_id = f"bench-{int(time.time())}"
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()

        model_results: list[ModelBenchmarkResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {
                pool.submit(_evaluate_model, adapter, cases): adapter
                for adapter in self.adapters
            }
            for future in as_completed(future_map):
                result = future.result()
                model_results.append(result)

        # Determine winners
        by_acc = sorted(model_results, key=lambda r: r.accuracy_pct, reverse=True)
        by_cost = sorted(model_results, key=lambda r: r.total_cost_usd)
        by_lat = sorted(model_results, key=lambda r: r.p50_latency_ms)

        run = BenchmarkRunResult(
            run_id=run_id,
            timestamp=ts,
            total_models=len(self.adapters),
            total_cases=len(cases),
            model_results=model_results,
            winner_accuracy=by_acc[0].model_id if by_acc else "",
            winner_cost=by_cost[0].model_id if by_cost else "",
            winner_latency=by_lat[0].model_id if by_lat else "",
        )
        return run


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_ADAPTER_MAP: dict[str, Any] = {
    "gemini":     GeminiAdapter,
    "claude":     ClaudeAdapter,
    "gpt4o":      GPT4oAdapter,
    "gpt4o-mini": lambda: LiteLLMAdapter("gpt-4o-mini"),
    "mock":       MockAdapter,
}


def _divider(char: str = "-", width: int = 72) -> str:
    return char * width


def _print_results(run: BenchmarkRunResult) -> None:
    print()
    print(_divider("="))
    print(f"  [BENCHMARK] Run ID: {run.run_id}  |  {run.timestamp}")
    print(f"  Models: {run.total_models}   Cases: {run.total_cases}")
    print(_divider("-"))
    print(f"  {'MODEL':<38} {'ACC%':>6} {'P50ms':>7} {'P90ms':>7} {'COST$':>9} {'ERR':>4}")
    print(_divider("-"))
    for r in run.ranked_by_accuracy():
        tag = ""
        if r.model_id == run.winner_accuracy:
            tag += "[ACC]"
        if r.model_id == run.winner_cost:
            tag += "[COST]"
        if r.model_id == run.winner_latency:
            tag += "[LAT]"
        print(
            f"  {r.model_id:<38} {r.accuracy_pct:>5.1f}% "
            f"{r.p50_latency_ms:>7.0f} {r.p90_latency_ms:>7.0f} "
            f"{r.total_cost_usd:>9.5f} {r.error_count:>4}  {tag}"
        )
    print(_divider("-"))
    print(f"  Winner by Accuracy : {run.winner_accuracy}")
    print(f"  Winner by Cost     : {run.winner_cost}")
    print(f"  Winner by Latency  : {run.winner_latency}")
    print(_divider("="))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="EARP Multi-Model Benchmark Runner")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(_ADAPTER_MAP.keys()),
        default=["mock"],
        help="Which models to benchmark",
    )
    parser.add_argument(
        "--workflow",
        choices=["refund", "cancel", "balance", "inventory", "subscription", "general"],
        help="Filter golden cases by workflow",
    )
    parser.add_argument("--max-cases", type=int, help="Limit to N cases per model")
    parser.add_argument("--dry-run", action="store_true", help="Use Mock adapter only")
    args = parser.parse_args()

    if args.dry_run:
        adapters = [MockAdapter()]
    else:
        adapters = [_ADAPTER_MAP[m]() for m in args.models]

    runner = BenchmarkRunner(adapters=adapters)
    run = runner.run(workflow=args.workflow, max_cases=args.max_cases)
    _print_results(run)


if __name__ == "__main__":
    main()
