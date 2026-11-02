"""L3 Self-Contradiction Oracle: Evaluates multi-turn state consistency and semantic alignment."""

from __future__ import annotations

from argvtix.scout.oracles.base import OracleLevel, OracleVerdict
from argvtix.scout.probes.base import ScoutProbe


class L3SelfContradictionOracle:
    """Detects when an agent contradicts statements or state assertions made in earlier turns."""

    def evaluate(
        self,
        conversation_history: list[dict[str, str]],
        probe: ScoutProbe,
    ) -> OracleVerdict:
        violations: list[str] = []

        # Extract assistant responses in order
        assistant_turns = [
            turn["content"]
            for turn in conversation_history
            if turn.get("role") == "assistant"
        ]

        if len(assistant_turns) < 2:
            return OracleVerdict(
                oracle_level=OracleLevel.L3_SELF_CONTRADICTION,
                passed=True,
                score=1.0,
                violations=[],
                reasoning="Single turn conversation: no contradiction possible.",
            )

        # Check order existence contradiction
        # E.g. Turn 1 talks about order status/items, Turn 2 claims order doesn't exist
        t1 = assistant_turns[0].lower()
        t_last = assistant_turns[-1].lower()

        t1_has_order = any(w in t1 for w in ["order is", "shipped", "delivered", "in transit", "placed on"])
        t_last_no_order = any(w in t_last for w in ["no such order", "order does not exist", "cannot find order", "not found in system"])

        if t1_has_order and t_last_no_order:
            violations.append(
                "Multi-Turn Contradiction: Assistant confirmed order details in turn 1, then claimed order does not exist in subsequent turn."
            )

        # Check return eligibility flip
        t1_electronics_returnable = "7 days" in t1 or "7-day" in t1 or "returnable" in t1
        t_last_milk_returnable = ("milk" in t_last or "dairy" in t_last) and any(
            phrase in t_last for phrase in ["can be returned", "return within 7 days", "eligible for return"]
        )
        if t1_electronics_returnable and t_last_milk_returnable and "milk" in t_last:
            violations.append(
                "Multi-Turn Contradiction: Assistant improperly applied electronics 7-day return policy to perishable dairy goods."
            )

        passed = len(violations) == 0
        score = 1.0 if passed else 0.0
        reasoning = "Multi-turn assertions are consistent." if passed else "; ".join(violations)

        return OracleVerdict(
            oracle_level=OracleLevel.L3_SELF_CONTRADICTION,
            passed=passed,
            score=score,
            violations=violations,
            reasoning=reasoning,
        )
