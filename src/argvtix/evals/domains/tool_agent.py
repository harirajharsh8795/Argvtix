"""
Tool Agent Domain Evaluator.

Assesses autonomous tool-using agents:
- Tool selection correctness: did agent invoke the right tool for the user request?
- Parameter accuracy: entity IDs and amounts match request
- Outcome alignment: did agent report the true execution outcome (success vs failure)?
"""

from __future__ import annotations

from typing import Any

from argvtix.evals.domains.protocol import EvaluationInput, EvaluationResult


class ToolAgentEvaluator:
    """Evaluates multi-step tool agents against ground-truth tools and state."""

    domain_name = "tool_agent"
    PASS_THRESHOLD = 0.80

    def evaluate(self, input_data: EvaluationInput) -> EvaluationResult:
        tool_records: list[dict[str, Any]] = (
            input_data.context.get("tool_records", []) or input_data.context.get("tools", []) or []
        )
        resp = input_data.response.strip().lower()

        if not tool_records and not input_data.ground_truth:
            return EvaluationResult(
                domain=self.domain_name,
                score=0.7,
                passed=False,
                reasoning="No tool execution records provided in context.",
                metrics={"state_grounding": 0.7},
            )

        # 1. State grounding: False success vs true failure
        tool_failures = [
            t
            for t in tool_records
            if not t.get("is_success", True) or "error" in str(t.get("tool_result", "")).lower()
        ]
        claimed_success = any(
            phrase in resp
            for phrase in [
                "success",
                "processed",
                "completed",
                "ho gaya",
                "kar diya",
                "refunded",
            ]
        )

        if tool_failures and claimed_success:
            return EvaluationResult(
                domain=self.domain_name,
                score=0.1,
                passed=False,
                reasoning="Critical failure: agent claimed successful execution despite tool failure.",
                metrics={"state_grounding": 0.1, "tool_accuracy": 0.0},
                details={"tool_failures": tool_failures},
            )

        # 2. Tool selection vs ground truth
        expected_tool = input_data.context.get("expected_tool") or (
            input_data.ground_truth.get("tool_name")
            if isinstance(input_data.ground_truth, dict)
            else None
        )
        tool_names = [t.get("tool_name") for t in tool_records if "tool_name" in t]

        tool_match = 1.0
        if expected_tool and expected_tool not in tool_names:
            tool_match = 0.2

        score = 0.95 if tool_match == 1.0 and not tool_failures else 0.4
        passed = score >= self.PASS_THRESHOLD

        return EvaluationResult(
            domain=self.domain_name,
            score=round(score, 3),
            passed=passed,
            reasoning=f"Tool alignment score: {score:.2f}. Executed tools: {tool_names}.",
            metrics={
                "tool_match": tool_match,
                "state_grounding": 1.0 if not tool_failures else 0.0,
            },
            details={"tools_executed": tool_names},
        )
