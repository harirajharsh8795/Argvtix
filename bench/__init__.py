"""
Argvtix Bench Package.

Standardized benchmark suite for evaluating reliability, policy enforcement,
safety boundaries, and hallucination detectors across AI customer support agents.
Includes 60+ labelled evaluation cases (40 dev + 20 held-out) across 13 failure types.
"""

from bench.runner import BenchmarkReport, BenchmarkRunner
from bench.taxonomy import FailureCategory, FailureTaxonomy

__all__ = [
    "BenchmarkReport",
    "BenchmarkRunner",
    "FailureCategory",
    "FailureTaxonomy",
]
