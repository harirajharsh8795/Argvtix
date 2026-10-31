"""
Policy Conflict Detection Module
Enterprise AI Reliability Platform (EARP)
"""
from earp.watchdog.conflicts.benchmark import (
    ConflictBenchmarkCase,
    build_conflict_benchmark_dataset,
    evaluate_conflict_benchmark,
)
from earp.watchdog.conflicts.detector import PolicyConflictDetector
from earp.watchdog.conflicts.schemas import (
    ConflictFinding,
    ConflictReport,
    ConflictVerdict,
    PolicyClause,
)

__all__ = [
    "PolicyClause",
    "ConflictFinding",
    "ConflictReport",
    "ConflictVerdict",
    "PolicyConflictDetector",
    "ConflictBenchmarkCase",
    "build_conflict_benchmark_dataset",
    "evaluate_conflict_benchmark",
]
