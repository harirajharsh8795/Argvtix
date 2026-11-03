"""
Replay Package.

Provides historical trace replaying, golden benchmark evaluation, and L0-L3 determinism verification.
"""

from argvtix.replay.engine import (
    CaseReplayResult,
    ReplayComparison,
    ReplayEngine,
    SuiteBenchmarkResult,
)
from argvtix.replay.golden import (
    GoldenCase,
    filter_golden_cases,
    get_golden_case,
    load_golden_cases,
)
from argvtix.replay.levels import (
    DeterminismReport,
    LevelReplayResult,
    LevelReplayRunner,
    ReplayLevel,
    ReproducibilityClass,
    StateSnapshot,
    compute_determinism_rate,
)

__all__ = [
    "CaseReplayResult",
    "DeterminismReport",
    "GoldenCase",
    "LevelReplayResult",
    "LevelReplayRunner",
    "ReplayComparison",
    "ReplayEngine",
    "ReplayLevel",
    "ReproducibilityClass",
    "StateSnapshot",
    "SuiteBenchmarkResult",
    "compute_determinism_rate",
    "filter_golden_cases",
    "get_golden_case",
    "load_golden_cases",
]
