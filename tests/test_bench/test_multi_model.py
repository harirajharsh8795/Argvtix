"""
Tests for Multi-Model Benchmark Module (src/argvtix/evals/benchmarks).
Verifies model adapters, multi-model parallel evaluation, winner determination, and reporting.
"""

from __future__ import annotations

import json

from argvtix.evals.benchmarks.adapters import MockAdapter, ModelResponse
from argvtix.evals.benchmarks.report import BenchmarkReport
from argvtix.evals.benchmarks.runner import BenchmarkRunner, _extract_intent


class TestModelAdapters:
    """Tests adapter interface and normalization."""

    def test_mock_adapter_generation(self):
        adapter = MockAdapter(fixed_text="Your refund request has been processed.")
        resp = adapter.generate("I want a refund for my order please")

        assert isinstance(resp, ModelResponse)
        assert resp.succeeded is True
        assert "refund" in resp.text.lower()
        assert resp.prompt_tokens > 0
        assert resp.completion_tokens > 0
        assert resp.cost_usd == 0.0
        assert resp.total_tokens == resp.prompt_tokens + resp.completion_tokens

    def test_extract_intent_heuristics(self):
        assert _extract_intent("Can I get a refund please") == "refund"
        assert _extract_intent("Cancel my pending shipment") == "cancel"
        assert _extract_intent("What is my current wallet balance") == "balance"
        assert _extract_intent("Hello, how are you doing?") == "general"


class TestBenchmarkRunnerMultiModel:
    """BenchmarkRunner execution, filtering, and aggregation."""

    def test_benchmark_runner_single_model_smoke(self):
        adapter = MockAdapter(fixed_text="Refund issued successfully.")
        runner = BenchmarkRunner(adapters=[adapter])

        result = runner.run(workflow="refund", max_cases=5)

        assert result.total_models == 1
        assert result.total_cases <= 5
        assert len(result.model_results) == 1

        mod_res = result.model_results[0]
        assert mod_res.model_id == adapter.model_id
        assert mod_res.total_cases > 0
        assert mod_res.accuracy_pct >= 0.0
        assert mod_res.p50_latency_ms >= 0.0

    def test_benchmark_runner_multi_model_winners(self):
        # Two mock adapters with different characteristics
        fast_adapter = MockAdapter(fixed_text="Your refund of 500 has been issued.")
        fast_adapter.model_id = "mock/fast-accurate"

        imperfect_adapter = MockAdapter(fixed_text="General greetings, how may I assist?")
        imperfect_adapter.model_id = "mock/slow-imperfect"

        runner = BenchmarkRunner(adapters=[fast_adapter, imperfect_adapter], max_workers=2)
        result = runner.run(workflow="refund", max_cases=4)

        assert result.total_models == 2
        ranked_acc = result.ranked_by_accuracy()
        assert len(ranked_acc) == 2
        # Accurate adapter should rank first
        assert ranked_acc[0].accuracy_pct >= ranked_acc[1].accuracy_pct

        ranked_cost = result.ranked_by_cost()
        assert len(ranked_cost) == 2

        ranked_lat = result.ranked_by_latency()
        assert len(ranked_lat) == 2

        assert result.winner_accuracy != ""
        assert result.winner_cost != ""
        assert result.winner_latency != ""


class TestBenchmarkReportGeneration:
    """BenchmarkReport formatting into Markdown and JSON."""

    def test_report_markdown_and_json(self):
        adapter = MockAdapter(fixed_text="Refund processed.")
        runner = BenchmarkRunner(adapters=[adapter])
        run_res = runner.run(max_cases=3)

        report = BenchmarkReport(run_res)
        md = report.to_markdown()
        assert "# Multi-Model Benchmark Report" in md
        assert "Winner Summary" in md
        assert f"`{adapter.model_id}`" in md

        raw_json = report.to_json()
        data = json.loads(raw_json)
        assert data["run_id"] == run_res.run_id
        assert data["total_models"] == 1
        assert len(data["models"]) == 1
