"""
Argvtix Regression Gate & Metric Comparator Package.
Enforces statistical, behavioral, and safety invariants between baseline and candidate runs.
"""

from argvtix.regression.comparator import (
    GateReport,
    GateVerdict,
    RegressionComparator,
    evaluate_regression_gate,
)

__all__ = [
    "GateReport",
    "GateVerdict",
    "RegressionComparator",
    "evaluate_regression_gate",
]
