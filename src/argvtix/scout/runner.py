"""Scout Runner: Orchestrates permission-first probe execution, safety checks, and report generation."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from argvtix.scout.oracles.engine import OracleEngine
from argvtix.scout.probes.base import (
    ProbeExecutionResult,
    ProbeSeverity,
    ScoutProbe,
)
from argvtix.scout.probes.registry import ProbeRegistry
from argvtix.scout.report import (
    AuditStatus,
    ScoutAuditReport,
    calculate_grade,
)
from argvtix.scout.safety import (
    ScoutSafetyController,
)
from argvtix.scout.scope import (
    ScopeConfig,
    validate_scope_allows_request,
)


class ScoutRunner:
    """Executes permission-governed security & reliability audits against AI chatbots."""

    def __init__(
        self,
        scope: ScopeConfig,
        probe_registry: ProbeRegistry | None = None,
        safety_controller: ScoutSafetyController | None = None,
        oracle_engine: OracleEngine | None = None,
    ):
        self.scope = scope
        self.probes = probe_registry or ProbeRegistry()
        self.safety = safety_controller or ScoutSafetyController(
            max_rpm=scope.max_rpm,
            max_turns_per_conversation=scope.max_turns_per_conversation,
            max_conversations=scope.max_conversations,
        )
        self.oracle_engine = oracle_engine or OracleEngine()

    def run_audit(
        self,
        target_fn: Callable[[str, list[dict[str, str]]], str],
        selected_probes: list[ScoutProbe] | None = None,
        auto_send_email: bool = False,
        k_trials: int = 5,
    ) -> ScoutAuditReport:
        """Executes the audit suite under strict safety and permission constraints.

        Args:
            target_fn: Callable accepting (user_input, history) -> agent_response_text
            selected_probes: Optional list of probes to run (defaults to full catalog)
            auto_send_email: STRICTLY MUST BE FALSE. If True, raises ScoutSafetyViolationError.
            k_trials: Number of trial repetitions per probe to compute real k/n reproducibility.
        """
        # 1. Blueprint Constraint: Enforce human review gate (NO auto-outreach)
        self.safety.enforce_human_review_gate(allow_auto_email=auto_send_email)

        # 2. Permission Constraint: Scope preflight check
        validate_scope_allows_request(self.scope, self.scope.target_url)

        probes_to_run = selected_probes or self.probes.list_all()
        findings: list[ProbeExecutionResult] = []

        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0

        category_scores: dict[str, list[float]] = {}

        for probe in probes_to_run:
            passed_trials = 0
            last_conv_history: list[dict[str, str]] = []
            all_violations: list[str] = []
            all_turn_scores: list[float] = []
            highest_oracle_level = "L1"

            for trial_idx in range(k_trials):
                # Check safety controller (kill switch, circuit breaker, rate limit)
                self.safety.check_safety_preflight(current_conversation_turns=0)
                self.safety.start_conversation()

                conv_history: list[dict[str, str]] = []
                trial_passed = True
                trial_violations: list[str] = []
                trial_scores: list[float] = []

                for turn in probe.turns:
                    self.safety.check_safety_preflight(current_conversation_turns=turn.turn_index)
                    self.safety.acquire_request_slot()

                    # Call target agent
                    try:
                        response_text = target_fn(turn.user_input, list(conv_history))
                        self.safety.record_response(200)
                    except Exception as e:
                        self.safety.record_response(500)
                        response_text = f"[TARGET_ERROR] {str(e)}"

                    conv_history.append({"role": "user", "content": turn.user_input})
                    conv_history.append({"role": "assistant", "content": response_text})

                    # Evaluate with Oracle Engine
                    verdict = self.oracle_engine.evaluate_probe_turn(
                        user_input=turn.user_input,
                        response_text=response_text,
                        probe=probe,
                        current_turn=turn,
                        conversation_history=conv_history,
                    )

                    trial_scores.append(verdict.aggregate_score)
                    if not verdict.passed:
                        trial_passed = False
                        trial_violations.extend(verdict.all_violations)

                    # Track oracle complexity level
                    for oracle_name in verdict.verdicts.keys():
                        if "L4" in oracle_name or "judge" in oracle_name.lower():
                            highest_oracle_level = "L4"
                        elif (
                            "L3" in oracle_name or "contradiction" in oracle_name.lower()
                        ) and highest_oracle_level != "L4":
                            highest_oracle_level = "L3"

                last_conv_history = conv_history
                all_turn_scores.extend(trial_scores)
                if trial_passed:
                    passed_trials += 1
                else:
                    all_violations.extend(trial_violations)

            avg_score = sum(all_turn_scores) / len(all_turn_scores) if all_turn_scores else 0.0
            category_scores.setdefault(probe.category.value, []).append(avg_score)

            probe_passed = passed_trials == k_trials
            reproducibility_str = f"{passed_trials}/{k_trials}"

            # Derive confidence strictly from oracle hierarchy
            if highest_oracle_level == "L4":
                confidence_str = "needs-review"
            elif highest_oracle_level == "L3":
                confidence_str = "likely"
            else:
                confidence_str = "confirmed"

            if not probe_passed:
                if probe.severity == ProbeSeverity.CRITICAL:
                    critical_count += 1
                elif probe.severity == ProbeSeverity.HIGH:
                    high_count += 1
                elif probe.severity == ProbeSeverity.MEDIUM:
                    medium_count += 1
                elif probe.severity == ProbeSeverity.LOW:
                    low_count += 1

            findings.append(
                ProbeExecutionResult(
                    probe_id=probe.probe_id,
                    category=probe.category,
                    severity=probe.severity,
                    passed=probe_passed,
                    conversation_history=last_conv_history,
                    violation_details="; ".join(sorted(set(all_violations)))
                    if all_violations
                    else None,
                    oracle_scores={"turn_scores": all_turn_scores, "avg_score": avg_score},
                    confidence=confidence_str,
                    reproducibility=reproducibility_str,
                    human_review_required=(confidence_str == "needs-review"),
                )
            )

        total = len(findings)
        passed = sum(1 for f in findings if f.passed)
        failed = total - passed
        pass_rate = (passed / total * 100.0) if total > 0 else 0.0

        cat_summary: dict[str, float] = {
            cat: round(sum(scores) / len(scores), 3) for cat, scores in category_scores.items()
        }

        grade = calculate_grade(
            critical_count=critical_count,
            high_count=high_count,
            pass_rate_pct=pass_rate,
        )

        return ScoutAuditReport(
            report_id=f"RPT-{uuid.uuid4().hex[:8].upper()}",
            scope_id=self.scope.scope_id,
            project_id=self.scope.project_id,
            target_name=self.scope.target_name,
            target_url=self.scope.target_url,
            target_tier=self.scope.target_tier,
            grade=grade,
            status=AuditStatus.DRAFT_PENDING_REVIEW,
            total_probes=total,
            passed_probes=passed,
            failed_probes=failed,
            pass_rate_percent=round(pass_rate, 1),
            critical_violations=critical_count,
            high_violations=high_count,
            medium_violations=medium_count,
            low_violations=low_count,
            category_scores=cat_summary,
            findings=findings,
        )
