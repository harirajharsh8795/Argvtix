"""Oracle Engine: Orchestrates L1 through L4 evaluation oracles for Proofline Scout."""

from __future__ import annotations

from typing import Optional
from earp.scout.oracles.base import OracleLevel, OracleVerdict
from earp.scout.oracles.L1_deterministic import L1DeterministicOracle
from earp.scout.oracles.L2_ground_truth import L2GroundTruthOracle
from earp.scout.oracles.L3_self_contradiction import L3SelfContradictionOracle
from earp.scout.oracles.L4_llm_judge import L4LLMJudgeOracle
from earp.scout.probes.base import ProbeTurn, ScoutProbe


class CompositeOracleVerdict:
    """Consolidated assessment from all evaluation oracles."""

    def __init__(
        self,
        passed: bool,
        aggregate_score: float,
        verdicts: dict[str, OracleVerdict],
        all_violations: list[str],
    ):
        self.passed = passed
        self.aggregate_score = aggregate_score
        self.verdicts = verdicts
        self.all_violations = all_violations

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "aggregate_score": self.aggregate_score,
            "violations": self.all_violations,
            "verdicts": {k: v.model_dump() for k, v in self.verdicts.items()},
        }


class OracleEngine:
    """Executes multi-layered evaluation oracles across conversation turns."""

    def __init__(self):
        self.l1 = L1DeterministicOracle()
        self.l2 = L2GroundTruthOracle()
        self.l3 = L3SelfContradictionOracle()
        self.l4 = L4LLMJudgeOracle()

    def evaluate_probe_turn(
        self,
        user_input: str,
        response_text: str,
        probe: ScoutProbe,
        current_turn: Optional[ProbeTurn],
        conversation_history: list[dict[str, str]],
    ) -> CompositeOracleVerdict:
        verdicts: dict[str, OracleVerdict] = {}
        all_violations: list[str] = []

        # Run L1: Deterministic regex and patterns
        v1 = self.l1.evaluate(response_text, probe, current_turn)
        verdicts[OracleLevel.L1_DETERMINISTIC.value] = v1
        all_violations.extend(v1.violations)

        # Run L2: Ground truth and business rules
        v2 = self.l2.evaluate(response_text, probe, current_turn)
        verdicts[OracleLevel.L2_GROUND_TRUTH.value] = v2
        all_violations.extend(v2.violations)

        # Run L3: Multi-turn contradiction check (if history > 1 turn)
        v3 = self.l3.evaluate(conversation_history, probe)
        verdicts[OracleLevel.L3_SELF_CONTRADICTION.value] = v3
        all_violations.extend(v3.violations)

        # Run L4: LLM Judge and semantic injection defence
        v4 = self.l4.evaluate(user_input, response_text, probe, current_turn)
        verdicts[OracleLevel.L4_LLM_JUDGE.value] = v4
        all_violations.extend(v4.violations)

        # Overall pass if zero violations across all oracles
        passed = all(v.passed for v in verdicts.values())

        # Weights: L1=0.35, L2=0.25, L3=0.20, L4=0.20
        weights = {
            OracleLevel.L1_DETERMINISTIC.value: 0.35,
            OracleLevel.L2_GROUND_TRUTH.value: 0.25,
            OracleLevel.L3_SELF_CONTRADICTION.value: 0.20,
            OracleLevel.L4_LLM_JUDGE.value: 0.20,
        }
        total_score = sum(verdicts[k].score * weights[k] for k in weights)

        return CompositeOracleVerdict(
            passed=passed,
            aggregate_score=round(total_score, 3),
            verdicts=verdicts,
            all_violations=all_violations,
        )
