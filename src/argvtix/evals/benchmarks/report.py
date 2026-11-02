"""
Benchmark Report Generator.

Produces a rich Markdown comparison table from a BenchmarkRunResult,
suitable for CI artefacts, Slack posts, or the React dashboard.
"""

from __future__ import annotations

import json
from pathlib import Path

from argvtix.evals.benchmarks.runner import BenchmarkRunResult


class BenchmarkReport:
    """Generate Markdown and JSON reports from a benchmark run."""

    def __init__(self, run: BenchmarkRunResult) -> None:
        self._run = run

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        r = self._run
        lines: list[str] = [
            "# Multi-Model Benchmark Report",
            "",
            f"**Run ID:** `{r.run_id}`  ",
            f"**Timestamp:** {r.timestamp}  ",
            f"**Golden Cases:** {r.total_cases}  ",
            f"**Models Evaluated:** {r.total_models}",
            "",
            "## Results",
            "",
            "| Model | Accuracy | P50 ms | P90 ms | Total Cost | Errors | Badges |",
            "|-------|----------|--------|--------|-----------|--------|--------|",
        ]
        for res in r.ranked_by_accuracy():
            badges = []
            if res.model_id == r.winner_accuracy:
                badges.append("🏆 Accuracy")
            if res.model_id == r.winner_cost:
                badges.append("💰 Cheapest")
            if res.model_id == r.winner_latency:
                badges.append("⚡ Fastest")
            lines.append(
                f"| `{res.model_id}` "
                f"| {res.accuracy_pct:.1f}% "
                f"| {res.p50_latency_ms:.0f} "
                f"| {res.p90_latency_ms:.0f} "
                f"| ${res.total_cost_usd:.5f} "
                f"| {res.error_count} "
                f"| {', '.join(badges) or '-'} |"
            )

        lines += [
            "",
            "## Winner Summary",
            "",
            f"- **Best Accuracy:** `{r.winner_accuracy}`",
            f"- **Lowest Cost:**   `{r.winner_cost}`",
            f"- **Fastest P50:**   `{r.winner_latency}`",
        ]

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON (for API / dashboard consumption)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        r = self._run
        return {
            "run_id": r.run_id,
            "timestamp": r.timestamp,
            "total_models": r.total_models,
            "total_cases": r.total_cases,
            "winner_accuracy": r.winner_accuracy,
            "winner_cost": r.winner_cost,
            "winner_latency": r.winner_latency,
            "models": [
                {
                    "model_id": res.model_id,
                    "accuracy_pct": round(res.accuracy_pct, 2),
                    "p50_latency_ms": round(res.p50_latency_ms, 1),
                    "p90_latency_ms": round(res.p90_latency_ms, 1),
                    "p95_latency_ms": round(res.p95_latency_ms, 1),
                    "total_cost_usd": round(res.total_cost_usd, 6),
                    "cost_per_100_usd": round(res.cost_per_100_usd, 4),
                    "passed": res.passed,
                    "failed": res.failed,
                    "errors": res.error_count,
                }
                for res in r.ranked_by_accuracy()
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, output_dir: str | Path = ".", prefix: str = "benchmark") -> dict[str, Path]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        md_path = out / f"{prefix}_{self._run.run_id}.md"
        json_path = out / f"{prefix}_{self._run.run_id}.json"

        md_path.write_text(self.to_markdown(), encoding="utf-8")
        json_path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

        return {"markdown": md_path, "json": json_path}
