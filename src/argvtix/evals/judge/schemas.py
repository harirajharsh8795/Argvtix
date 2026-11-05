"""
LLM Judge Data Models and Schemas (MISSING-01).

Defines:
- JudgeRubric: Scoring dimensions and weights
- JudgeVerdict: Output of judge evaluation with dimensional scoring, injection checks, and assessment mode
- JudgeCalibrationResult: Cohen's Kappa agreement metric vs human gold standard
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RubricDimension(BaseModel):
    weight: float
    max_score: float = 10.0
    description: str
    levels: dict[int, str] = Field(default_factory=dict)


class JudgeRubric(BaseModel):
    version: str = "2.0"
    rubric_name: str = "enterprise_agent_reliability_rubric"
    dimensions: dict[str, RubricDimension] = Field(default_factory=dict)
    min_overall_score: float = 8.0
    zero_tolerance_penalties: dict[str, float] = Field(default_factory=dict)


class JudgeVerdict(BaseModel):
    """Result of an LLM Judge evaluation for a candidate response."""

    case_id: str = Field(default="")
    overall_score: float = Field(..., ge=0.0, le=10.0)
    passed: bool = Field(...)
    reasoning: str = Field(default="")
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    is_injection_suspected: bool = Field(default=False)
    injection_details: str | None = Field(default=None)
    penalties_applied: list[str] = Field(default_factory=list)
    assessment_mode: str = Field(
        default="judge-assessed",
        description="Assessment mode: 'judge-assessed' or 'mock-assessed'",
    )
    is_mock: bool = Field(
        default=False,
        description="True if evaluated by a mock judge rather than a real LLM",
    )
    review_status: str = Field(
        default="needs-review",
        description="Judge-only findings must always be labeled needs-review",
    )


class CalibrationCase(BaseModel):
    """Human-labelled case used for inter-rater agreement calibration."""

    id: str
    domain: str
    language: str
    input_prompt: str
    agent_response: str
    tool_executed: str = ""
    tool_status: str = "success"
    gold_score: float
    expected_verdict: str
    human_rationale: str = ""


class JudgeCalibrationResult(BaseModel):
    """Inter-rater reliability report between automated Judge and human labels."""

    total_cases: int
    cohens_kappa: float
    raw_agreement_percentage: float
    pearson_correlation: float
    mean_absolute_error: float
    calibrated: bool = Field(..., description="True if Cohen's Kappa >= 0.70")
    model_name: str = Field(default="", description="Model identifier used for evaluation")
    assessment_mode: str = Field(
        default="judge-assessed",
        description="Assessment mode: 'judge-assessed' or 'mock-assessed'",
    )
    is_mock: bool = Field(
        default=False,
        description="True if calibration used a mock judge",
    )
    details: list[dict[str, Any]] = Field(default_factory=list)
