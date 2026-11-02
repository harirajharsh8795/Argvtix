"""
Policy Conflict Detection Schemas
Enterprise AI Reliability Platform (ARGVTIX)
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConflictVerdict(str, Enum):
    CONFLICT = "conflict"
    CONSISTENT = "consistent"
    UNCLEAR = "unclear"


class PolicyClause(BaseModel):
    """An individual clause extracted from a policy or SOP document."""

    clause_id: str
    doc_id: str
    doc_title: str
    topic: (
        str  # e.g., 'refund_window', 'approval_threshold', 'cancellation_window', 'data_retention'
    )
    text: str
    numeric_value: float | None = None
    unit: str | None = None  # e.g., 'days', 'inr', 'hours'
    condition: str | None = None


class ConflictFinding(BaseModel):
    """A detected conflict between two policy clauses."""

    conflict_id: str
    topic: str
    clause_a: PolicyClause
    clause_b: PolicyClause
    verdict: ConflictVerdict
    severity: str = "high"  # 'low' | 'medium' | 'high' | 'critical'
    explanation: str
    citation_a: str
    citation_b: str


class ConflictReport(BaseModel):
    """Aggregate report of policy conflict detection scan."""

    total_clauses_scanned: int
    pairs_evaluated: int
    conflicts_detected: int
    consistent_pairs: int
    unclear_pairs: int
    findings: list[ConflictFinding] = Field(default_factory=list)
    precision: float = 100.0
    recall: float = 100.0
    f1_score: float = 100.0
