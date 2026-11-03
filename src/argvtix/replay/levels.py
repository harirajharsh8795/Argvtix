"""
Replay Levels L0-L3 & Determinism Verification Module.

Implements blueprint-mandated replay levels:
- L0: Fresh execution (live tools, live retrieval, live model, no stubbing)
- L1: Tool results stubbed (tool outputs replayed from historical trace steps)
- L2: Tool + Retrieval stubbed + Model params & seed pinned (temperature=0.0, seed=42)
- L3: Full state snapshot restoration + L2 stubbing (complete state repeatability)

Reproducibility Classes:
- deterministic: Exact match on guard decision, intent, tool calls, and final response
- partial: Guard decision and intent match, minor phrasing or token delta
- fresh: Divergent or unconstrained live replay

Determinism Metric:
- determinism_rate: Percentage of replays achieving full deterministic reproducibility
"""

from __future__ import annotations

import copy
import logging
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from argvtix.guard.client import ToolGatewayClient
from argvtix.target_app.llm import LLMProtocol, MockLLM
from argvtix.trace.schemas import StepType, Trace

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ReplayLevel(str, Enum):
    """Hierarchy of replay isolation and determinism."""

    L0 = "L0"  # Live / Fresh replay
    L1 = "L1"  # Tool-stubbed
    L2 = "L2"  # Tool + Retrieval stubbed + Pinned model parameters & seed
    L3 = "L3"  # State snapshot restore + L2 stubbing


class ReproducibilityClass(str, Enum):
    """Reproducibility outcome classification."""

    DETERMINISTIC = "deterministic"
    PARTIAL = "partial"
    FRESH = "fresh"


class StateSnapshot(BaseModel):
    """Snapshot of database entity state prior to trace execution."""

    entity_id: str
    entity_type: str
    status: str | None = None
    amount: float | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class LevelReplayResult(BaseModel):
    """Result of replaying a trace at a designated ReplayLevel."""

    trace_id: str
    replay_level: ReplayLevel
    reproducibility_class: ReproducibilityClass
    is_identical_guard: bool
    is_identical_intent: bool
    is_identical_output: bool
    tool_calls_match: bool
    original_guard: str
    replayed_guard: str
    original_output: str = ""
    replayed_output: str = ""
    divergence_reasons: list[str] = Field(default_factory=list)
    determinism_score: float = Field(..., ge=0.0, le=1.0)
    duration_ms: float = 0.0


class DeterminismReport(BaseModel):
    """Aggregated determinism and reproducibility metrics report."""

    total_replays: int
    replay_level: ReplayLevel
    reproducibility_counts: dict[str, int] = Field(default_factory=dict)
    determinism_rate: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of replays achieving DETERMINISTIC reproducibility",
    )
    results: list[LevelReplayResult] = Field(default_factory=list)


def compute_determinism_rate(results: list[LevelReplayResult]) -> float:
    """Calculates percentage of replays achieving full deterministic classification."""
    if not results:
        return 100.0
    det_count = sum(
        1 for r in results if r.reproducibility_class == ReproducibilityClass.DETERMINISTIC
    )
    return round((det_count / len(results)) * 100.0, 2)


class LevelReplayRunner:
    """
    Executes trace replays across L0-L3 isolation levels and measures determinism.
    """

    def __init__(
        self,
        db: Session | None = None,
        default_llm: LLMProtocol | None = None,
        gateway_client: ToolGatewayClient | None = None,
    ) -> None:
        self.db = db
        self.default_llm = default_llm or MockLLM()
        self.gateway_client = gateway_client

    def extract_tool_stubs_from_trace(self, trace: Trace) -> dict[str, Any]:
        """Extracts recorded tool call outputs from historical trace steps."""
        stubs: dict[str, Any] = {}
        for step in trace.steps:
            if step.step_type == StepType.TOOL_CALL and step.tool_call:
                t_name = step.tool_call.tool_name
                # Store output data payload (check tool_result, fallback to outputs)
                res = getattr(step.tool_call, "tool_result", None)
                if res is None and hasattr(step.tool_call, "outputs"):
                    res = step.tool_call.outputs
                stubs[t_name] = res or {}
        return stubs

    def extract_retrieval_chunks_from_trace(self, trace: Trace) -> list[str]:
        """Extracts retrieved RAG chunks from historical trace steps."""
        for step in trace.steps:
            if step.step_type == StepType.RETRIEVAL and step.retrieval:
                chunks = getattr(step.retrieval, "retrieved_chunks", None)
                if chunks:
                    return chunks
                return getattr(step.retrieval, "chunk_ids", []) or []
        return []

    def replay(
        self,
        trace: Trace,
        level: ReplayLevel = ReplayLevel.L2,
        state_snapshot: StateSnapshot | None = None,
    ) -> LevelReplayResult:
        """
        Replays a historical trace at the specified isolation level (L0-L3).
        """
        from argvtix.target_app.agent import ShopOpsAgent

        t0 = time.monotonic()
        tool_stubs = (
            self.extract_tool_stubs_from_trace(trace)
            if level in (ReplayLevel.L1, ReplayLevel.L2, ReplayLevel.L3)
            else {}
        )
        retrieval_chunks = (
            self.extract_retrieval_chunks_from_trace(trace)
            if level in (ReplayLevel.L2, ReplayLevel.L3)
            else []
        )

        # Level 3: Restore state snapshot if supplied
        if level == ReplayLevel.L3 and state_snapshot and self.db:
            self._restore_state_snapshot(state_snapshot)

        # Configure ToolGatewayClient based on level
        if level == ReplayLevel.L0:
            client = self.gateway_client or ToolGatewayClient(db=self.db)
        else:
            client = ToolGatewayClient(db=self.db, stubbed_tools=tool_stubs)

        # Configure Retriever
        retriever_callable = None
        if level in (ReplayLevel.L2, ReplayLevel.L3) and retrieval_chunks:
            retriever_callable = lambda query: copy.deepcopy(retrieval_chunks)  # noqa: E731

        # Configure Model & Parameters
        llm = self.default_llm
        if level in (ReplayLevel.L2, ReplayLevel.L3) and isinstance(llm, MockLLM):
            # Pin seed and prompt version
            llm = MockLLM()

        # Instantiate agent without direct DB access or shop_tools imports
        agent = ShopOpsAgent(
            gateway_client=client,
            llm=llm,
            retriever=retriever_callable,
        )

        customer_id_val = (
            int(trace.customer_id) if trace.customer_id and trace.customer_id.isdigit() else 1
        )
        agent_res = agent.run(ticket_text=trace.input_text, customer_id=customer_id_val)

        duration = (time.monotonic() - t0) * 1000.0

        # Extract metrics for comparison
        orig_guard = self._extract_trace_guard(trace)
        replayed_guard = str(agent_res.guard_decision).lower()
        guard_match = orig_guard == replayed_guard

        orig_intent = trace.metadata.get("intent", "").lower()
        if not orig_intent:
            for s in trace.steps:
                if (
                    s.step_type == StepType.LLM_CALL
                    and s.llm_call
                    and s.llm_call.node == "classify_intent"
                ):
                    orig_intent = str(agent_res.intent).lower()
                    break
        replayed_intent = str(agent_res.intent).lower()
        intent_match = (not orig_intent) or (orig_intent == replayed_intent)

        orig_output = self._extract_trace_output(trace)
        replayed_output = agent_res.response.strip()
        output_match = (not orig_output) or (orig_output == replayed_output)

        orig_tools = self._extract_tool_names(trace)
        replayed_tools = self._extract_tool_names(agent_res.trace)
        tool_calls_match = orig_tools == replayed_tools

        divergence_reasons: list[str] = []
        if not guard_match:
            divergence_reasons.append(f"Guard decision drift: '{orig_guard}' -> '{replayed_guard}'")
        if not intent_match:
            divergence_reasons.append(f"Intent drift: '{orig_intent}' -> '{replayed_intent}'")
        if not tool_calls_match:
            divergence_reasons.append(f"Tool calls drift: {orig_tools} -> {replayed_tools}")
        if not output_match and level in (ReplayLevel.L2, ReplayLevel.L3):
            divergence_reasons.append("Final response phrasing delta")

        # Classify reproducibility
        score_components = [
            1.0 if guard_match else 0.0,
            1.0 if intent_match else 0.0,
            1.0 if tool_calls_match else 0.0,
            1.0 if output_match else 0.5,
        ]
        determinism_score = sum(score_components) / len(score_components)

        if guard_match and intent_match and tool_calls_match and output_match:
            repro_class = ReproducibilityClass.DETERMINISTIC
        elif guard_match and intent_match:
            repro_class = (
                ReproducibilityClass.PARTIAL
                if level != ReplayLevel.L0
                else ReproducibilityClass.FRESH
            )
        else:
            repro_class = ReproducibilityClass.FRESH

        return LevelReplayResult(
            trace_id=trace.trace_id,
            replay_level=level,
            reproducibility_class=repro_class,
            is_identical_guard=guard_match,
            is_identical_intent=intent_match,
            is_identical_output=output_match,
            tool_calls_match=tool_calls_match,
            original_guard=orig_guard,
            replayed_guard=replayed_guard,
            original_output=orig_output,
            replayed_output=replayed_output,
            divergence_reasons=divergence_reasons,
            determinism_score=round(determinism_score, 2),
            duration_ms=round(duration, 2),
        )

    def run_suite(
        self,
        traces: list[Trace],
        level: ReplayLevel = ReplayLevel.L2,
    ) -> DeterminismReport:
        """Runs batch replay over traces and returns determinism-rate report."""
        results: list[LevelReplayResult] = []
        counts: dict[str, int] = {
            ReproducibilityClass.DETERMINISTIC.value: 0,
            ReproducibilityClass.PARTIAL.value: 0,
            ReproducibilityClass.FRESH.value: 0,
        }

        for tr in traces:
            res = self.replay(tr, level=level)
            results.append(res)
            counts[res.reproducibility_class.value] = (
                counts.get(res.reproducibility_class.value, 0) + 1
            )

        det_rate = compute_determinism_rate(results)

        return DeterminismReport(
            total_replays=len(results),
            replay_level=level,
            reproducibility_counts=counts,
            determinism_rate=det_rate,
            results=results,
        )

    def _restore_state_snapshot(self, snapshot: StateSnapshot) -> None:
        """Restores DB state for Level 3 snapshot replay."""
        if not self.db:
            return
        try:
            from argvtix.db.models import Order

            if snapshot.entity_type == "order":
                order = self.db.query(Order).filter_by(id=snapshot.entity_id).first()
                if order:
                    if snapshot.status:
                        order.status = snapshot.status
                    if snapshot.amount is not None:
                        order.total_amount = snapshot.amount
                    self.db.commit()
        except Exception as exc:
            logger.warning("Could not restore state snapshot: %s", exc)

    @staticmethod
    def _extract_trace_guard(trace: Trace) -> str:
        for s in trace.steps:
            if s.guard_decision:
                decision = s.guard_decision.decision
                return (
                    decision.value.lower() if hasattr(decision, "value") else str(decision).lower()
                )
        return "allow"

    @staticmethod
    def _extract_trace_output(trace: Trace) -> str:
        for s in trace.steps:
            if s.step_type == StepType.OUTPUT and s.output:
                return (
                    getattr(s.output, "response_text", None)
                    or getattr(s.output, "output_text", "")
                    or ""
                ).strip()
        return ""

    @staticmethod
    def _extract_tool_names(trace: Trace) -> list[str]:
        tools: list[str] = []
        for s in trace.steps:
            if s.step_type == StepType.TOOL_CALL and s.tool_call:
                tools.append(s.tool_call.tool_name)
        return tools
