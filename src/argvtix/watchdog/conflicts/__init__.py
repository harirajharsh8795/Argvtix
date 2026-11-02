"""
Policy Conflict Detection Module
Enterprise AI Reliability Platform (ARGVTIX)
"""

from argvtix.watchdog.conflicts.benchmark import (
    ConflictBenchmarkCase,
    build_conflict_benchmark_dataset,
    evaluate_conflict_benchmark,
)
from argvtix.watchdog.conflicts.detector import PolicyConflictDetector
from argvtix.watchdog.conflicts.schemas import (
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
