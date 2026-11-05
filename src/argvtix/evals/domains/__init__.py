"""
Domain Evaluators Registry and Unified Factory.
"""

from __future__ import annotations

from argvtix.evals.domains.code import CodeAgentEvaluator
from argvtix.evals.domains.protocol import DomainEvaluator, EvaluationInput, EvaluationResult
from argvtix.evals.domains.rag import RAGEvaluator
from argvtix.evals.domains.text_qa import TextQAEvaluator
from argvtix.evals.domains.tool_agent import ToolAgentEvaluator

_REGISTRY: dict[str, type[DomainEvaluator]] = {
    "text_qa": TextQAEvaluator,
    "rag": RAGEvaluator,
    "tool_agent": ToolAgentEvaluator,
    "code": CodeAgentEvaluator,
}


def get_evaluator(domain: str) -> DomainEvaluator:
    """Retrieve an evaluator instance for a specific evaluation domain."""
    cls = _REGISTRY.get(domain.lower())
    if not cls:
        raise ValueError(
            f"Unknown evaluation domain: '{domain}'. Supported: {list(_REGISTRY.keys())}"
        )
    return cls()


__all__ = [
    "DomainEvaluator",
    "EvaluationInput",
    "EvaluationResult",
    "TextQAEvaluator",
    "RAGEvaluator",
    "ToolAgentEvaluator",
    "CodeAgentEvaluator",
    "get_evaluator",
]
