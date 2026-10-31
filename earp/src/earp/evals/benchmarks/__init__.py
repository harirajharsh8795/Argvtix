"""
Multi-Model Live Benchmarking Package.

Runs evaluation golden cases across multiple LLM providers
(Gemini, Claude, GPT-4o, LiteLLM-compatible) and compares
accuracy, latency, and cost side-by-side.
"""
from earp.evals.benchmarks.adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    GPT4oAdapter,
    LiteLLMAdapter,
    ModelAdapter,
)
from earp.evals.benchmarks.runner import BenchmarkRunner, BenchmarkRunResult
from earp.evals.benchmarks.report import BenchmarkReport

__all__ = [
    "ModelAdapter",
    "GeminiAdapter",
    "ClaudeAdapter",
    "GPT4oAdapter",
    "LiteLLMAdapter",
    "BenchmarkRunner",
    "BenchmarkRunResult",
    "BenchmarkReport",
]
