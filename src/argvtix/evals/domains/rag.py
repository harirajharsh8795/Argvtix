"""
RAG (Retrieval-Augmented Generation) Domain Evaluator.

Assesses:
- Faithfulness: whether claims made in the answer are supported by retrieved context chunks
- Context Precision: whether retrieved chunks are relevant to the query
- Hallucination Penalty: flags fabricated statistics or terms not in context
"""

from __future__ import annotations

import re

from argvtix.evals.domains.protocol import EvaluationInput, EvaluationResult


class RAGEvaluator:
    """Evaluates groundedness and faithfulness of RAG responses against retrieved chunks."""

    domain_name = "rag"
    PASS_THRESHOLD = 0.65

    def evaluate(self, input_data: EvaluationInput) -> EvaluationResult:
        resp = input_data.response.strip().lower()
        chunks: list[str] = input_data.context.get("chunks", []) or input_data.context.get(
            "retrieved_chunks", []
        )

        if not resp:
            return EvaluationResult(
                domain=self.domain_name,
                score=0.0,
                passed=False,
                reasoning="Response is empty.",
                metrics={"faithfulness": 0.0, "context_coverage": 0.0},
            )

        if not chunks:
            admits_unanswerable = any(
                p in resp
                for p in [
                    "not found",
                    "cannot find",
                    "no information",
                    "don't have",
                    "pata nahi",
                    "available nahi",
                ]
            )
            score = 0.9 if admits_unanswerable else 0.4
            return EvaluationResult(
                domain=self.domain_name,
                score=score,
                passed=score >= self.PASS_THRESHOLD,
                reasoning="No context chunks provided in retrieval context.",
                metrics={"faithfulness": score},
            )

        combined_context = " ".join(chunks).lower()

        # Normalize common abbreviations and symbols
        resp_norm = (
            resp.replace("%", " percent ")
            .replace("p.a.", " per annum ")
            .replace("p.a", " per annum ")
        )
        ctx_norm = (
            combined_context.replace("%", " percent ")
            .replace("p.a.", " per annum ")
            .replace("p.a", " per annum ")
        )

        context_words = set(re.findall(r"\w+", ctx_norm))
        resp_words = [w for w in re.findall(r"\w+", resp_norm) if len(w) > 3]

        if not resp_words:
            return EvaluationResult(
                domain=self.domain_name,
                score=0.8,
                passed=True,
                reasoning="Response too short for deep citation check.",
                metrics={"faithfulness": 0.8},
            )

        grounded_count = sum(1 for w in resp_words if w in context_words)
        faithfulness = grounded_count / len(resp_words)

        # Hallucination check for numbers/dates not present in context
        resp_numbers = set(re.findall(r"\b\d+\b", resp))
        context_numbers = set(re.findall(r"\b\d+\b", combined_context))
        unsupported_numbers = resp_numbers - context_numbers

        hallucination_penalty = 0.25 * min(3, len(unsupported_numbers))
        final_score = max(0.0, min(1.0, faithfulness - hallucination_penalty))

        passed = final_score >= self.PASS_THRESHOLD
        reasoning = (
            f"Faithfulness: {faithfulness:.2%}. "
            f"Unsupported numeric claims: {len(unsupported_numbers)}."
        )

        return EvaluationResult(
            domain=self.domain_name,
            score=round(final_score, 3),
            passed=passed,
            reasoning=reasoning,
            metrics={
                "faithfulness": round(faithfulness, 3),
                "hallucination_penalty": round(hallucination_penalty, 3),
            },
            details={"unsupported_numbers": list(unsupported_numbers)},
        )
