"""
Test Suite for Trace Schemas — 20 tests covering:

1-5:   Valid trace creation (happy paths)
6-10:  Invalid data rejection (validation)
11-15: Edge cases (empty steps, boundary values, etc.)
16-20: Aggregation, helper methods, serialization

Run with: pytest tests/test_trace/ -v
"""

import pytest

from argvtix.trace.schemas import (
    SHOPOPS_WORKFLOWS,
    GuardDecision,
    GuardDecisionData,
    LLMCallData,
    OutputData,
    RetrievalData,
    Severity,
    StepType,
    ToolCallData,
    Trace,
    TraceStatus,
    TraceStep,
    WorkflowType,
)

# ──────────────────────────────────────────────
# Helper Factories — Create common test objects quickly
# ──────────────────────────────────────────────


def make_llm_step(index: int = 0, **overrides) -> TraceStep:
    """Create a valid LLM call step."""
    data = {
        "model": "gemini-2.0-flash",
        "prompt_version": "v3",
        "input_text": "order 1042 ka refund de do",
        "output_text": "Processing refund for order 1042",
        "input_tokens": 150,
        "output_tokens": 50,
        "total_tokens": 200,
        "cost_usd": 0.002,
        "latency_ms": 1200.0,
    }
    data.update(overrides)
    return TraceStep(
        step_index=index,
        step_type=StepType.LLM_CALL,
        llm_call=LLMCallData(**data),
        duration_ms=data.get("latency_ms", 1200.0),
    )


def make_retrieval_step(index: int = 1, **overrides) -> TraceStep:
    """Create a valid retrieval step."""
    data = {
        "query": "refund policy for damaged items",
        "method": "hybrid_rerank",
        "chunk_ids": ["chunk_7", "chunk_12", "chunk_3"],
        "scores": [0.92, 0.87, 0.81],
    }
    data.update(overrides)
    return TraceStep(
        step_index=index,
        step_type=StepType.RETRIEVAL,
        retrieval=RetrievalData(**data),
        duration_ms=45.0,
    )


def make_tool_step(index: int = 2, **overrides) -> TraceStep:
    """Create a valid tool call step."""
    data = {
        "tool_name": "issue_refund",
        "tool_args": {"order_id": 1042, "amount": 2500, "reason": "damaged"},
        "tool_result": {"status": "success", "refund_id": "ref_001"},
        "is_success": True,
        "is_write": True,
    }
    data.update(overrides)
    return TraceStep(
        step_index=index,
        step_type=StepType.TOOL_CALL,
        tool_call=ToolCallData(**data),
        duration_ms=200.0,
    )


def make_guard_step(index: int = 3, decision: GuardDecision = GuardDecision.ALLOW) -> TraceStep:
    """Create a valid guard decision step."""
    return TraceStep(
        step_index=index,
        step_type=StepType.GUARD_DECISION,
        guard_decision=GuardDecisionData(
            action="issue_refund",
            entity_id="order_1042",
            checks_performed=["ownership", "duplicate", "limit"],
            checks_passed=["ownership", "duplicate", "limit"],
            checks_failed=[],
            decision=decision,
            reasons=["All checks passed"],
            policy_version="policy_v1",
        ),
        duration_ms=15.0,
    )


def make_output_step(index: int = 4) -> TraceStep:
    """Create a valid output step."""
    return TraceStep(
        step_index=index,
        step_type=StepType.OUTPUT,
        output=OutputData(
            response_text="Amit ji, aapke order #1042 ka ₹2,500 refund process ho gaya hai.",
            language="hinglish",
            citations=["chunk_7"],
            pii_masked=True,
        ),
        duration_ms=5.0,
    )


def make_trace(**overrides) -> Trace:
    """Create a valid trace with default values."""
    data = {
        "input_text": "order 1042 ka refund de do",
        "prompt_version": "v3",
        "model_version": "gemini-2.0-flash",
        "customer_id": "cust_001",
    }
    data.update(overrides)
    return Trace(**data)


# ──────────────────────────────────────────────
# TEST GROUP 1: Valid Trace Creation (Happy Paths)
# Tests 1-5
# ──────────────────────────────────────────────


class TestValidTraceCreation:
    """Test that valid traces are created correctly."""

    def test_01_minimal_trace(self):
        """A trace with just required fields should work."""
        trace = Trace(
            input_text="hello",
            prompt_version="v1",
            model_version="gemini-2.0-flash",
        )
        assert trace.trace_id.startswith("tr-")
        assert trace.status == TraceStatus.IN_PROGRESS
        assert trace.steps == []
        assert trace.total_cost_usd == 0.0

    def test_02_full_trace_with_all_steps(self):
        """A trace with all step types should serialize correctly."""
        trace = make_trace()
        trace.add_step(make_llm_step())
        trace.add_step(make_retrieval_step())
        trace.add_step(make_tool_step())
        trace.add_step(make_guard_step())
        trace.add_step(make_output_step())

        assert len(trace.steps) == 5
        assert trace.steps[0].step_type == StepType.LLM_CALL
        assert trace.steps[1].step_type == StepType.RETRIEVAL
        assert trace.steps[2].step_type == StepType.TOOL_CALL
        assert trace.steps[3].step_type == StepType.GUARD_DECISION
        assert trace.steps[4].step_type == StepType.OUTPUT

    def test_03_trace_completion(self):
        """Completing a trace should compute aggregates."""
        trace = make_trace()
        trace.add_step(make_llm_step())
        trace.add_step(make_retrieval_step())
        trace.add_step(make_output_step())
        trace.complete()

        assert trace.status == TraceStatus.COMPLETED
        assert trace.completed_at is not None
        assert trace.step_count == 3
        assert trace.total_tokens == 200  # From the LLM step
        assert trace.total_cost_usd == 0.002

    def test_04_trace_json_roundtrip(self):
        """A trace should serialize to JSON and back without data loss."""
        trace = make_trace()
        trace.add_step(make_llm_step())
        trace.add_step(make_guard_step())

        json_str = trace.model_dump_json()
        restored = Trace.model_validate_json(json_str)

        assert restored.trace_id == trace.trace_id
        assert restored.input_text == trace.input_text
        assert len(restored.steps) == 2
        assert restored.steps[0].llm_call.model == "gemini-2.0-flash"

    def test_05_trace_with_tags_and_metadata(self):
        """Tags and metadata should be stored correctly."""
        trace = make_trace(
            tags=["refund", "hindi", "high_value"],
            metadata={"ticket_id": "TKT-001", "priority": "high"},
        )
        assert "refund" in trace.tags
        assert trace.metadata["ticket_id"] == "TKT-001"


# ──────────────────────────────────────────────
# TEST GROUP 2: Invalid Data Rejection (Validation)
# Tests 6-10
# ──────────────────────────────────────────────


class TestValidation:
    """Test that invalid data is properly rejected."""

    def test_06_empty_input_text_rejected(self):
        """Trace with empty input text should be rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Trace(
                input_text="   ",
                prompt_version="v1",
                model_version="gemini",
            )

    def test_07_negative_cost_rejected(self):
        """Negative cost should be rejected."""
        with pytest.raises(ValueError):
            LLMCallData(
                model="gemini",
                prompt_version="v1",
                input_text="test",
                input_tokens=100,
                cost_usd=-0.5,  # Negative! Should fail
            )

    def test_08_negative_tokens_rejected(self):
        """Negative token count should be rejected."""
        with pytest.raises(ValueError):
            LLMCallData(
                model="gemini",
                prompt_version="v1",
                input_text="test",
                input_tokens=-10,  # Negative! Should fail
            )

    def test_09_mismatched_step_type_and_data(self):
        """Step type 'llm_call' but with retrieval data should fail."""
        with pytest.raises(ValueError, match="data is missing"):
            TraceStep(
                step_index=0,
                step_type=StepType.LLM_CALL,
                retrieval=RetrievalData(query="test", method="vector"),
                # llm_call data is missing!
            )

    def test_10_mismatched_chunk_ids_and_scores(self):
        """chunk_ids and scores with different lengths should fail."""
        with pytest.raises(ValueError, match="same length"):
            RetrievalData(
                query="test",
                method="vector",
                chunk_ids=["c1", "c2", "c3"],
                scores=[0.9, 0.8],  # Only 2 scores for 3 chunks!
            )


# ──────────────────────────────────────────────
# TEST GROUP 3: Edge Cases
# Tests 11-15
# ──────────────────────────────────────────────


class TestEdgeCases:
    """Test boundary conditions and edge cases."""

    def test_11_trace_with_no_steps(self):
        """A trace with zero steps should be valid (just created, not used yet)."""
        trace = make_trace()
        assert len(trace.steps) == 0
        trace.complete()
        assert trace.step_count == 0
        assert trace.total_cost_usd == 0.0

    def test_12_duplicate_step_index_rejected(self):
        """Two steps with the same index should be rejected."""
        with pytest.raises(ValueError, match="Duplicate step_index"):
            Trace(
                input_text="test",
                prompt_version="v1",
                model_version="gemini",
                steps=[
                    make_llm_step(index=0),
                    make_retrieval_step(index=0),  # Duplicate index!
                ],
            )

    def test_13_out_of_order_steps_rejected(self):
        """Steps not in ascending order should be rejected."""
        with pytest.raises(ValueError, match="must be in order"):
            Trace(
                input_text="test",
                prompt_version="v1",
                model_version="gemini",
                steps=[
                    make_retrieval_step(index=2),  # Out of order!
                    make_llm_step(index=0),
                ],
            )

    def test_14_zero_token_llm_call(self):
        """An LLM call with 0 tokens should be valid (edge case)."""
        step = make_llm_step(input_tokens=0, output_tokens=0, total_tokens=0)
        assert step.llm_call.total_tokens == 0

    def test_15_auto_compute_total_tokens(self):
        """total_tokens should auto-compute from input + output if not set."""
        data = LLMCallData(
            model="gemini",
            prompt_version="v1",
            input_text="hello",
            input_tokens=100,
            output_tokens=50,
            # total_tokens not set — should auto-compute to 150
        )
        assert data.total_tokens == 150


# ──────────────────────────────────────────────
# TEST GROUP 4: Helper Methods & Aggregation
# Tests 16-20
# ──────────────────────────────────────────────


class TestHelperMethods:
    """Test trace helper methods and computations."""

    def test_16_add_step_auto_indexes(self):
        """add_step() should auto-set step_index."""
        trace = make_trace()
        step1 = TraceStep(
            step_index=999,  # Will be overridden
            step_type=StepType.LLM_CALL,
            llm_call=LLMCallData(
                model="gemini",
                prompt_version="v1",
                input_text="test",
                input_tokens=10,
            ),
        )
        step2 = TraceStep(
            step_index=999,  # Will be overridden
            step_type=StepType.OUTPUT,
            output=OutputData(response_text="done"),
        )
        trace.add_step(step1)
        trace.add_step(step2)
        assert trace.steps[0].step_index == 0
        assert trace.steps[1].step_index == 1

    def test_17_get_steps_by_type(self):
        """get_steps_by_type should filter correctly."""
        trace = make_trace()
        trace.add_step(make_llm_step())
        trace.add_step(make_retrieval_step())
        trace.add_step(make_llm_step())  # Second LLM call

        llm_steps = trace.get_steps_by_type(StepType.LLM_CALL)
        assert len(llm_steps) == 2

        retrieval_steps = trace.get_steps_by_type(StepType.RETRIEVAL)
        assert len(retrieval_steps) == 1

    def test_18_has_write_operations(self):
        """has_write_operations should detect write tool calls."""
        trace = make_trace()
        trace.add_step(make_llm_step())
        assert trace.has_write_operations() is False

        trace.add_step(make_tool_step(is_write=True))
        assert trace.has_write_operations() is True

    def test_19_was_blocked(self):
        """was_blocked should detect BLOCK guard decisions."""
        trace = make_trace()
        trace.add_step(make_guard_step(decision=GuardDecision.ALLOW))
        assert trace.was_blocked() is False

        trace2 = make_trace()
        trace2.add_step(make_guard_step(index=0, decision=GuardDecision.BLOCK))
        assert trace2.was_blocked() is True

    def test_20_shopops_workflows_defined(self):
        """All 6 ShopOps workflows should be defined correctly."""
        assert len(SHOPOPS_WORKFLOWS) == 6
        workflow_types = {w.workflow_type for w in SHOPOPS_WORKFLOWS}
        assert WorkflowType.REFUND in workflow_types
        assert WorkflowType.CANCEL_ORDER in workflow_types
        assert WorkflowType.CLOSE_TICKET in workflow_types
        assert WorkflowType.UPDATE_INVENTORY in workflow_types
        assert WorkflowType.CHANGE_SUBSCRIPTION in workflow_types
        assert WorkflowType.BALANCE_QUERY in workflow_types

        # Refund should require approval above ₹10K
        refund = next(w for w in SHOPOPS_WORKFLOWS if w.workflow_type == WorkflowType.REFUND)
        assert refund.requires_approval_above == 10000.0
        assert refund.risk_level == Severity.HIGH
