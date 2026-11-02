"""
Multi-Model Live Benchmarking Package.

Runs evaluation golden cases across multiple LLM providers
(Gemini, Claude, GPT-4o, LiteLLM-compatible) and compares
accuracy, latency, and cost side-by-side.
"""

from argvtix.evals.benchmarks.adapters import (
    ClaudeAdapter,
    GeminiAdapter,
    GPT4oAdapter,
    LiteLLMAdapter,
    ModelAdapter,
)
from argvtix.evals.benchmarks.report import BenchmarkReport
from argvtix.evals.benchmarks.runner import BenchmarkRunner, BenchmarkRunResult

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
