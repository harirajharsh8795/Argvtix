"""Base schemas for Scout evaluation oracles."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class OracleLevel(str, Enum):
    """Evaluation oracle hierarchy."""
    L1_DETERMINISTIC = "L1_DETERMINISTIC"          # Regex, keywords, PII, SQL leakage
    L2_GROUND_TRUTH = "L2_GROUND_TRUTH"            # Policy bounds & ground truth rules
    L3_SELF_CONTRADICTION = "L3_SELF_CONTRADICTION"  # Multi-turn state consistency
    L4_LLM_JUDGE = "L4_LLM_JUDGE"                  # Semantic rubric & safety evaluation


class OracleVerdict(BaseModel):
    """Verdict produced by an individual evaluation oracle."""
    oracle_level: OracleLevel
    passed: bool
    score: float = Field(ge=0.0, le=1.0, description="1.0 = fully compliant, 0.0 = severe violation")
    violations: list[str] = Field(default_factory=list)
    reasoning: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
