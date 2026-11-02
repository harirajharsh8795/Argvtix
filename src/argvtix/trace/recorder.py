"""
Trace Recorder — attaches ARGVTIX trace recording hooks onto the agent's execution.

Every node in the LangGraph agent calls these hooks so that each LLM call,
retrieval, tool use, and guard decision is persisted as a TraceStep matching
the core Pydantic v2 schemas.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from argvtix.trace.schemas import (
    ErrorData,
    GuardDecision,
    GuardDecisionData,
    LLMCallData,
    OutputData,
    RetrievalData,
    StepType,
    ToolCallData,
    Trace,
    TraceStatus,
    TraceStep,
)


class TraceRecorder:
    """
    Accumulates TraceStep objects during a single agent run.
    Call .build_trace() at the end to get the complete Trace object.
    """

    def __init__(
        self,
        input_text: str,
        session_id: str | None = None,
        workflow_id: str = "wf-shopops-support",
        customer_id: str | int | None = None,
        prompt_version: str = "v1",
        model_version: str = "gemini-2.0-flash",
    ) -> None:
        self.trace_id = f"tr-{uuid.uuid4().hex[:12]}"
        self.input_text = input_text
        self.session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
        self.workflow_id = workflow_id
        self.customer_id = str(customer_id) if customer_id is not None else None
        self.prompt_version = prompt_version
        self.model_version = model_version
        self.started_at = datetime.now(UTC)
        self._steps: list[TraceStep] = []

    def _next_index(self) -> int:
        return len(self._steps)

    # ------------------------------------------------------------------
    # Recording helpers — one per node type
    # ------------------------------------------------------------------

    def record_llm_call(
        self,
        node: str,
        model: str,
        prompt: str,
        response: str,
        latency_ms: float,
        prompt_tokens: int = 15,
        completion_tokens: int = 25,
    ) -> None:
        step = TraceStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            step_index=self._next_index(),
            step_type=StepType.LLM_CALL,
            timestamp=datetime.now(UTC),
            duration_ms=latency_ms,
            metadata={"node": node},
            llm_call=LLMCallData(
                model=model,
                prompt_version=self.prompt_version,
                input_text=prompt[:500],
                output_text=response[:500],
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                latency_ms=latency_ms,
            ),
        )
        self._steps.append(step)

    def record_retrieval(
        self,
        node: str,
        query: str,
        retrieved_chunks: list[str],
        latency_ms: float,
    ) -> None:
        chunk_ids = [f"chk-{idx + 1}" for idx in range(len(retrieved_chunks))]
        scores = [round(1.0 - (idx * 0.1), 2) for idx in range(len(retrieved_chunks))]

        step = TraceStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            step_index=self._next_index(),
            step_type=StepType.RETRIEVAL,
            timestamp=datetime.now(UTC),
            duration_ms=latency_ms,
            metadata={"node": node},
            retrieval=RetrievalData(
                query=query,
                method="bm25",
                chunk_ids=chunk_ids,
                scores=scores,
                num_results=len(retrieved_chunks),
                latency_ms=latency_ms,
            ),
        )
        self._steps.append(step)

    def record_tool_call(
        self,
        node: str,
        tool_name: str,
        inputs: dict,
        outputs: dict,
        latency_ms: float,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        is_write = any(w in tool_name for w in ("refund", "cancel", "update", "create", "delete"))
        step = TraceStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            step_index=self._next_index(),
            step_type=StepType.TOOL_CALL,
            timestamp=datetime.now(UTC),
            duration_ms=latency_ms,
            metadata={"node": node, "error": error} if error else {"node": node},
            tool_call=ToolCallData(
                tool_name=tool_name,
                tool_args=inputs,
                tool_result=outputs,
                is_success=success,
                is_write=is_write,
                latency_ms=latency_ms,
            ),
        )
        self._steps.append(step)

    def record_guard_decision(
        self,
        node: str,
        action_type: str,
        action_params: dict,
        decision: str | GuardDecision,
        reason: str,
        latency_ms: float,
        policy_triggered: str | None = None,
    ) -> None:
        if isinstance(decision, str):
            dec_enum = GuardDecision(decision.lower())
        else:
            dec_enum = decision

        reasons = [reason] if reason else []
        entity_id = str(action_params.get("order_id")) if action_params.get("order_id") else None

        step = TraceStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            step_index=self._next_index(),
            step_type=StepType.GUARD_DECISION,
            timestamp=datetime.now(UTC),
            duration_ms=latency_ms,
            metadata={"node": node, "policy_triggered": policy_triggered},
            guard_decision=GuardDecisionData(
                action=action_type,
                entity_id=entity_id,
                checks_performed=[policy_triggered] if policy_triggered else ["policy_check"],
                checks_passed=[] if dec_enum == GuardDecision.BLOCK else ["policy_check"],
                checks_failed=[policy_triggered]
                if dec_enum == GuardDecision.BLOCK and policy_triggered
                else [],
                decision=dec_enum,
                reasons=reasons,
                policy_version="1.0.0",
            ),
        )
        self._steps.append(step)

    def record_output(
        self,
        node: str,
        response_text: str,
        latency_ms: float = 0.0,
    ) -> None:
        step = TraceStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            step_index=self._next_index(),
            step_type=StepType.OUTPUT,
            timestamp=datetime.now(UTC),
            duration_ms=latency_ms,
            metadata={"node": node},
            output=OutputData(
                response_text=response_text,
                language="hinglish",
                citations=[],
                pii_masked=False,
            ),
        )
        self._steps.append(step)

    def record_error(
        self,
        node: str,
        error_type: str,
        message: str,
    ) -> None:
        step = TraceStep(
            step_id=f"step-{uuid.uuid4().hex[:8]}",
            step_index=self._next_index(),
            step_type=StepType.ERROR,
            timestamp=datetime.now(UTC),
            duration_ms=0.0,
            metadata={"node": node},
            error=ErrorData(
                error_type=error_type,
                error_message=message,
                is_recoverable=False,
            ),
        )
        self._steps.append(step)

    # ------------------------------------------------------------------
    # Build final Trace
    # ------------------------------------------------------------------

    def build_trace(
        self,
        status: str | TraceStatus = TraceStatus.COMPLETED,
        total_cost_usd: float = 0.0,
    ) -> Trace:
        finished_at = datetime.now(UTC)
        total_ms = (finished_at - self.started_at).total_seconds() * 1000

        total_tokens = sum(
            step.llm_call.total_tokens for step in self._steps if step.llm_call is not None
        )

        trace_status = TraceStatus(status.lower()) if isinstance(status, str) else status

        return Trace(
            trace_id=self.trace_id,
            session_id=self.session_id,
            customer_id=self.customer_id,
            input_text=self.input_text,
            input_language="hinglish",
            prompt_version=self.prompt_version,
            model_version=self.model_version,
            steps=self._steps,
            status=trace_status,
            created_at=self.started_at,
            completed_at=finished_at,
            total_tokens=total_tokens,
            total_cost_usd=total_cost_usd,
            total_latency_ms=total_ms,
            step_count=len(self._steps),
            metadata={"workflow_id": self.workflow_id},
        )
