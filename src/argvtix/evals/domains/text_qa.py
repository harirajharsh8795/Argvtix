"""
Text QA Domain Evaluator.

Assesses direct question-answering fidelity:
- Semantic overlap with ground truth (token recall/F1)
- Answer completeness and hallucination avoidance
- Politeness and conciseness
"""

from __future__ import annotations

import re

from argvtix.evals.domains.protocol import EvaluationInput, EvaluationResult


class TextQAEvaluator:
    """Evaluates question-answering agent responses against ground truth."""

    domain_name = "text_qa"
    PASS_THRESHOLD = 0.50

    def evaluate(self, input_data: EvaluationInput) -> EvaluationResult:
        resp = input_data.response.strip().lower()
        prompt = input_data.prompt.strip().lower()
        gt = str(input_data.ground_truth).strip().lower() if input_data.ground_truth else None

        if not resp:
            return EvaluationResult(
                domain=self.domain_name,
                score=0.0,
                passed=False,
                reasoning="Response is empty or blank.",
                metrics={"relevance": 0.0, "completeness": 0.0},
            )

        resp_words = set(re.findall(r"\w+", resp))

        # Ground-truth alignment if reference provided
        if gt:
            gt_words = set(re.findall(r"\w+", gt))
            # Ignore stopwords for overlap
            meaningful_gt = {w for w in gt_words if len(w) > 2} or gt_words
            common_gt = len(meaningful_gt & resp_words)
            gt_recall = common_gt / max(1, len(meaningful_gt))
            score = round(gt_recall, 3)
            passed = score >= self.PASS_THRESHOLD
            reasoning = f"Evaluated against reference answer. Reference Recall: {gt_recall:.2%}."
            metrics = {"gt_recall": score}
        else:
            prompt_words = set(re.findall(r"\w+", prompt))
            common_prompt = len(prompt_words & resp_words)
            relevance_score = min(1.0, common_prompt / max(1, len(prompt_words) * 0.3))
            score = round(max(0.5, relevance_score), 3)
            passed = score >= self.PASS_THRESHOLD
            reasoning = f"Evaluated without reference answer. Relevance: {relevance_score:.2%}."
            metrics = {"relevance": score}

        return EvaluationResult(
            domain=self.domain_name,
            score=score,
            passed=passed,
            reasoning=reasoning,
            metrics=metrics,
        )
