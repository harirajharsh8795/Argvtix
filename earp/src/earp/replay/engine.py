"""
Replay Engine — Rerun historical traces or golden test cases against candidate models & prompts.

Features:
- Historical trace replay: Re-executes the exact user ticket with a new model/prompt and computes deltas.
- Golden case evaluation: Evaluates agent output and guard decisions against ground-truth expectations.
- Suite benchmark runner: Runs all 50 golden benchmark cases and outputs aggregate accuracy metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from earp.replay.golden import GoldenCase, load_golden_cases
from earp.target_app.agent import ShopOpsAgent
from earp.target_app.llm import LLMProtocol, get_default_llm
from earp.trace.schemas import Trace
from earp.trace.store import get_trace


@dataclass
class ReplayComparison:
    """Side-by-side comparison between original historical trace and replayed run."""
    trace_id: str
    original_status: str
    replayed_status: str
    original_latency_ms: float
    replayed_latency_ms: float
    latency_delta_ms: float
    original_tokens: int
    replayed_tokens: int
    tokens_delta: int
    original_guard_decision: str
    replayed_guard_decision: str
    guard_decisions_match: bool
    replayed_trace: Trace


@dataclass
class CaseReplayResult:
    """Result of running agent on a single ground-truth golden case."""
    case_id: str
    workflow: str
    ticket_text: str
    expected_intent: str
    actual_intent: str
    intent_match: bool
    expected_guard: str
    actual_guard: str
    guard_match: bool
    is_passed: bool
    response: str
    trace_id: str
    latency_ms: float
    failure_reasons: list[str] = field(default_factory=list)


@dataclass
class SuiteBenchmarkResult:
    """Summary of running a batch of golden cases."""
    total_cases: int
    passed_cases: int
    failed_cases: int
    accuracy_percent: float
    intent_accuracy_percent: float
    guard_accuracy_percent: float
    case_results: list[CaseReplayResult] = field(default_factory=list)


class ReplayEngine:
    """
    Coordinates trace replay, golden benchmark execution, and version comparisons.
    """

    def __init__(self, db: Session, default_llm: LLMProtocol | None = None) -> None:
        self.db = db
        self.default_llm = default_llm or get_default_llm()

    def replay_trace(
        self,
        trace_id: str,
        candidate_llm: LLMProtocol | None = None,
        candidate_prompt_version: str = "v2",
    ) -> ReplayComparison:
        """
        Fetch historical trace from database, re-execute the agent using the candidate LLM
        or prompt version, and compute delta metrics.
        """
        orig_trace = get_trace(self.db, trace_id)
        if not orig_trace:
            raise ValueError(f"Trace {trace_id} not found in database.")

        llm = candidate_llm or self.default_llm
        agent = ShopOpsAgent(
            db=self.db,
            llm=llm,
            workflow_id=orig_trace.metadata.get("workflow_id", "wf-shopops-support"),
        )

        customer_id_val = int(orig_trace.customer_id) if orig_trace.customer_id and orig_trace.customer_id.isdigit() else 1
        agent_res = agent.run(
            ticket_text=orig_trace.input_text,
            customer_id=customer_id_val,
        )

        replayed_trace = agent_res.trace
        orig_status = orig_trace.status.value
        rep_status = replayed_trace.status.value

        # Extract guard decisions
        orig_guard = "allow"
        for s in orig_trace.steps:
            if s.guard_decision:
                orig_guard = (
                    s.guard_decision.decision.value
                    if hasattr(s.guard_decision.decision, "value")
                    else str(s.guard_decision.decision)
                )

        rep_guard = str(agent_res.guard_decision).lower()

        lat_delta = replayed_trace.total_latency_ms - orig_trace.total_latency_ms
        tok_delta = replayed_trace.total_tokens - orig_trace.total_tokens

        return ReplayComparison(
            trace_id=trace_id,
            original_status=orig_status,
            replayed_status=rep_status,
            original_latency_ms=orig_trace.total_latency_ms,
            replayed_latency_ms=replayed_trace.total_latency_ms,
            latency_delta_ms=lat_delta,
            original_tokens=orig_trace.total_tokens,
            replayed_tokens=replayed_trace.total_tokens,
            tokens_delta=tok_delta,
            original_guard_decision=orig_guard,
            replayed_guard_decision=rep_guard,
            guard_decisions_match=(orig_guard.lower() == rep_guard.lower()),
            replayed_trace=replayed_trace,
        )

    def replay_case(
        self,
        case: GoldenCase,
        llm: LLMProtocol | None = None,
    ) -> CaseReplayResult:
        """
        Evaluate a single ground-truth golden case against the agent.
        """
        target_llm = llm or self.default_llm
        agent = ShopOpsAgent(db=self.db, llm=target_llm)

        cust_id = int(case.customer_id.replace("cust_", "")) if case.customer_id.startswith("cust_") and case.customer_id.replace("cust_", "").isdigit() else 1

        res = agent.run(
            ticket_text=case.ticket_text,
            customer_id=cust_id,
        )

        actual_intent = str(res.intent).lower()
        exp_intent = case.expected_intent.lower()
        intent_match = (actual_intent == exp_intent)

        actual_guard = str(res.guard_decision).lower()
        exp_guard = case.expected_guard_decision.lower()
        guard_match = (actual_guard == exp_guard)

        failure_reasons: list[str] = []
        if not intent_match:
            failure_reasons.append(f"Intent mismatch: expected '{exp_intent}', got '{actual_intent}'")
        if not guard_match:
            failure_reasons.append(f"Guard mismatch: expected '{exp_guard}', got '{actual_guard}'")

        is_passed = intent_match and guard_match

        return CaseReplayResult(
            case_id=case.id,
            workflow=case.workflow,
            ticket_text=case.ticket_text,
            expected_intent=exp_intent,
            actual_intent=actual_intent,
            intent_match=intent_match,
            expected_guard=exp_guard,
            actual_guard=actual_guard,
            guard_match=guard_match,
            is_passed=is_passed,
            response=res.response,
            trace_id=res.trace.trace_id,
            latency_ms=res.trace.total_latency_ms,
            failure_reasons=failure_reasons,
        )

    def run_suite(
        self,
        cases: list[GoldenCase] | None = None,
        llm: LLMProtocol | None = None,
    ) -> SuiteBenchmarkResult:
        """
        Run a full evaluation suite against golden cases.
        """
        test_cases = cases or load_golden_cases()
        results: list[CaseReplayResult] = []

        for c in test_cases:
            res = self.replay_case(c, llm=llm)
            results.append(res)

        total = len(results)
        passed = sum(1 for r in results if r.is_passed)
        failed = total - passed
        intent_matches = sum(1 for r in results if r.intent_match)
        guard_matches = sum(1 for r in results if r.guard_match)

        acc = (passed / total * 100.0) if total > 0 else 0.0
        intent_acc = (intent_matches / total * 100.0) if total > 0 else 0.0
        guard_acc = (guard_matches / total * 100.0) if total > 0 else 0.0

        return SuiteBenchmarkResult(
            total_cases=total,
            passed_cases=passed,
            failed_cases=failed,
            accuracy_percent=round(acc, 1),
            intent_accuracy_percent=round(intent_acc, 1),
            guard_accuracy_percent=round(guard_acc, 1),
            case_results=results,
        )
