"""Argvtix Scout Probe Modules and Base Schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProbeCategory(str, Enum):
    """The 12 Scout audit probe categories."""

    PROMPT_INJECTION = "PROMPT_INJECTION"
    PII_LEAKAGE = "PII_LEAKAGE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    STATE_DESYNC = "STATE_DESYNC"
    COMPETITOR_HALLUCINATION = "COMPETITOR_HALLUCINATION"
    TOXICITY_TONE = "TOXICITY_TONE"
    BROKEN_TOOL = "BROKEN_TOOL"
    ARITHMETIC_ERROR = "ARITHMETIC_ERROR"
    CITATION_FORGERY = "CITATION_FORGERY"
    SPLICED_CONTEXT = "SPLICED_CONTEXT"
    MULTILINGUAL_JAILBREAK = "MULTILINGUAL_JAILBREAK"


class ProbeSeverity(str, Enum):
    """Audit finding severity."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ProbeTurn(BaseModel):
    """A single turn in a multi-turn probe conversation."""

    turn_index: int = Field(default=1, ge=1)
    user_input: str = Field(description="Adversarial or functional test input sent to agent")
    expected_behavior: str = Field(
        default="", description="Expected safe response pattern or refusal"
    )
    unacceptable_keywords: list[str] = Field(
        default_factory=list,
        description="Phrases or strings indicating failure if present in response",
    )


class ScoutProbe(BaseModel):
    """Specification for an audit probe scenario."""

    probe_id: str
    category: ProbeCategory
    name: str
    description: str
    severity: ProbeSeverity = ProbeSeverity.HIGH
    turns: list[ProbeTurn] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProbeExecutionResult(BaseModel):
    """Outcome of executing a ScoutProbe against a target chatbot."""

    probe_id: str
    category: ProbeCategory
    severity: ProbeSeverity
    passed: bool
    conversation_history: list[dict[str, str]] = Field(
        default_factory=list, description="Sequence of {'role': 'user'|'assistant', 'content': str}"
    )
    violation_details: str | None = None
    oracle_scores: dict[str, Any] = Field(default_factory=dict)
    confidence: str = Field(
        default="confirmed",
        description="Confidence label: 'confirmed', 'likely', or 'needs-review'",
    )
    reproducibility: str = Field(
        default="3/3",
        description="k/n trial reproducibility",
    )
    human_review_required: bool = Field(default=False)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
