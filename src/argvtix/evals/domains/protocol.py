"""
Domain Evaluator Protocol & Unified Evaluation Schema.

Defines the contract for domain-specialized evaluators:
- text_qa: Question answering fidelity, semantic relevance, ground-truth alignment
- rag: Context faithfulness, retrieval precision, citation accuracy
- tool_agent: Tool selection precision, parameter validity, state-grounding
- code: Syntax validity, test pass capability, dangerous call inspection
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class EvaluationInput(BaseModel):
    """Input payload provided to a domain evaluator."""

    prompt: str = Field(..., description="User query, prompt, or instruction")
    response: str = Field(..., description="Agent or model generated response text")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Execution context: retrieved chunks, tool logs, state snapshots",
    )
    ground_truth: Any = Field(
        default=None,
        description="Optional reference answer, expected tool call, or expected state",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata tags")


class EvaluationResult(BaseModel):
    """Standardized result returned by all domain evaluators."""

    domain: str = Field(..., description="Domain name (text_qa, rag, tool_agent, code)")
    score: float = Field(..., ge=0.0, le=1.0, description="Normalized score 0.0 to 1.0")
    passed: bool = Field(..., description="Binary pass/fail verdict against threshold")
    reasoning: str = Field(..., description="Structured explanation of evaluation")
    metrics: dict[str, float] = Field(
        default_factory=dict, description="Sub-metrics (e.g. faithfulness, precision)"
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional domain-specific diagnostic details"
    )


@runtime_checkable
class DomainEvaluator(Protocol):
    """Protocol that all domain-specific evaluators must implement."""

    domain_name: str

    def evaluate(self, input_data: EvaluationInput) -> EvaluationResult:
        """Evaluate agent output in this domain and return structured result."""
        ...
