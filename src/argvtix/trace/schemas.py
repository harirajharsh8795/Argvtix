"""
Trace Schemas — Pydantic models for recording AI agent interactions.

Every AI interaction is a Trace. Every Trace has multiple TraceSteps.
Think of it like a movie (Trace) made up of scenes (TraceSteps).

Example Trace:
    Customer asks: "order 1042 ka refund de do"

    Step 1 (llm_call): AI reads the request, thinks about what to do
    Step 2 (retrieval): AI fetches refund policy from vector store
    Step 3 (guard_decision): Guard checks if refund is allowed
    Step 4 (tool_call): AI calls issue_refund(order=1042, amount=2500)
    Step 5 (output): AI replies "Aapka refund process ho gaya hai"
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ──────────────────────────────────────────────
# Enums — Predefined choices for step types, status, etc.
# ──────────────────────────────────────────────


class StepType(str, Enum):
    """The 7 types of steps an AI agent can take."""

    LLM_CALL = "llm_call"  # AI model inference
    RETRIEVAL = "retrieval"  # RAG: fetching docs/chunks
    TOOL_CALL = "tool_call"  # Calling a business tool (refund, cancel, etc.)
    GUARD_DECISION = "guard_decision"  # Safety check before action
    APPROVAL = "approval"  # Human-in-the-loop approval
    OUTPUT = "output"  # Final response to user
    ERROR = "error"  # Something went wrong


class GuardDecision(str, Enum):
    """What the guard decided to do."""

    ALLOW = "allow"  # Safe to proceed
    BLOCK = "block"  # Dangerous, stop immediately
    ASK_HUMAN = "ask_human"  # Risky, need human approval


class ApprovalStatus(str, Enum):
    """Human approval decision."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"  # Approved but with modifications


class TraceStatus(str, Enum):
    """Overall status of the trace."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Stopped by guard


class Severity(str, Enum):
    """Severity levels for findings/alerts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ──────────────────────────────────────────────
# TraceStep Models — One model per step type
# ──────────────────────────────────────────────


class LLMCallData(BaseModel):
    """Data specific to an LLM call step."""

    model: str = Field(..., description="Model name, e.g. 'gemini-2.0-flash'")
    prompt_version: str = Field(..., description="Version tag of the prompt template, e.g. 'v3'")
    system_prompt_hash: str | None = Field(
        default=None, description="Hash of the system prompt for change detection"
    )
    input_text: str = Field(..., description="The input sent to the model")
    output_text: str | None = Field(default=None, description="The model's response")
    input_tokens: int = Field(..., ge=0, description="Number of input tokens")
    output_tokens: int = Field(default=0, ge=0, description="Number of output tokens")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens used")
    cost_usd: float = Field(default=0.0, ge=0.0, description="Cost in USD for this call")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Latency in milliseconds")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    is_structured_output: bool = Field(
        default=False, description="Whether structured output (JSON mode) was used"
    )

    @model_validator(mode="after")
    def compute_total_tokens(self) -> LLMCallData:
        """Auto-compute total tokens if not provided."""
        if self.total_tokens == 0 and (self.input_tokens > 0 or self.output_tokens > 0):
            self.total_tokens = self.input_tokens + self.output_tokens
        return self


class RetrievalData(BaseModel):
    """Data specific to a retrieval (RAG) step."""

    query: str = Field(..., description="The search query")
    rewritten_query: str | None = Field(
        default=None, description="Query after LLM rewriting, if applied"
    )
    method: str = Field(
        ..., description="Retrieval method: 'vector', 'bm25', 'hybrid', 'hybrid_rerank'"
    )
    chunk_ids: list[str] = Field(default_factory=list, description="IDs of retrieved chunks")
    retrieved_chunks: list[str] = Field(
        default_factory=list, description="Text content of retrieved chunks"
    )
    scores: list[float] = Field(default_factory=list, description="Relevance scores per chunk")
    num_results: int = Field(default=0, ge=0, description="Number of results returned")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Retrieval latency in ms")

    @model_validator(mode="after")
    def validate_chunks_and_scores(self) -> RetrievalData:
        """Ensure chunk_ids and scores have the same length."""
        if self.chunk_ids and self.scores and len(self.chunk_ids) != len(self.scores):
            raise ValueError(
                f"chunk_ids ({len(self.chunk_ids)}) and scores ({len(self.scores)}) "
                f"must have the same length"
            )
        if self.num_results == 0 and self.chunk_ids:
            self.num_results = len(self.chunk_ids)
        return self


class ToolCallData(BaseModel):
    """Data specific to a tool/MCP call step."""

    tool_name: str = Field(..., description="Name of the tool, e.g. 'issue_refund'")
    tool_args: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the tool"
    )
    tool_result: Any | None = Field(default=None, description="Result returned by the tool")
    is_success: bool = Field(default=True, description="Whether the tool call succeeded")
    is_write: bool = Field(
        default=False, description="Whether this tool modifies data (vs read-only)"
    )
    mcp_server: str | None = Field(
        default=None, description="MCP server name if called via MCP protocol"
    )
    latency_ms: float = Field(default=0.0, ge=0.0)


class GuardDecisionData(BaseModel):
    """Data specific to a guard (safety check) step."""

    action: str = Field(..., description="The action being checked, e.g. 'issue_refund'")
    entity_id: str | None = Field(
        default=None, description="The entity being acted on, e.g. 'order_1042'"
    )
    checks_performed: list[str] = Field(
        default_factory=list,
        description="List of checks run, e.g. ['ownership', 'duplicate', 'limit']",
    )
    checks_passed: list[str] = Field(default_factory=list, description="Checks that passed")
    checks_failed: list[str] = Field(default_factory=list, description="Checks that failed")
    decision: GuardDecision = Field(..., description="ALLOW, BLOCK, or ASK_HUMAN")
    reasons: list[str] = Field(
        default_factory=list, description="Human-readable reasons for the decision"
    )
    policy_version: str | None = Field(default=None, description="Version of the policy YAML used")


class ApprovalData(BaseModel):
    """Data specific to a human approval step."""

    action: str = Field(..., description="The action awaiting approval")
    original_args: dict[str, Any] = Field(default_factory=dict, description="Original arguments")
    edited_args: dict[str, Any] | None = Field(
        default=None, description="Modified arguments (if human edited)"
    )
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    reviewer: str | None = Field(default=None, description="Who approved/rejected")
    reason: str | None = Field(default=None, description="Reason for approval/rejection")
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = Field(default=None)


class OutputData(BaseModel):
    """Data specific to the final output step."""

    response_text: str = Field(..., description="The final response sent to the user")
    language: str | None = Field(
        default=None, description="Detected language: 'en', 'hi', 'hinglish'"
    )
    citations: list[str] = Field(
        default_factory=list, description="Chunk IDs cited in the response"
    )
    pii_masked: bool = Field(default=False, description="Whether PII was masked in output")


class ErrorData(BaseModel):
    """Data specific to an error step."""

    error_type: str = Field(..., description="Exception class name")
    error_message: str = Field(..., description="Error message")
    stack_trace: str | None = Field(default=None, description="Full stack trace")
    is_recoverable: bool = Field(default=False, description="Whether the agent recovered")


# ──────────────────────────────────────────────
# TraceStep — One step in the AI's journey
# ──────────────────────────────────────────────


class TraceStep(BaseModel):
    """
    A single step in an AI trace.

    Each step represents one action the AI agent took:
    - An LLM call
    - A retrieval from the vector store
    - A tool call (refund, cancel, etc.)
    - A guard safety check
    - A human approval
    - The final output
    - An error
    """

    step_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this step",
    )
    step_index: int = Field(..., ge=0, description="Order of this step (0-based)")
    step_type: StepType = Field(..., description="Type of step")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this step started",
    )

    # Step-specific data — only ONE of these should be set per step
    llm_call: LLMCallData | None = Field(default=None)
    retrieval: RetrievalData | None = Field(default=None)
    tool_call: ToolCallData | None = Field(default=None)
    guard_decision: GuardDecisionData | None = Field(default=None)
    approval: ApprovalData | None = Field(default=None)
    output: OutputData | None = Field(default=None)
    error: ErrorData | None = Field(default=None)

    # Metadata
    duration_ms: float | None = Field(default=None, ge=0.0, description="Step duration in ms")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra key-value pairs")

    @model_validator(mode="after")
    def validate_step_data_matches_type(self) -> TraceStep:
        """Ensure the step data field matches the step type."""
        type_to_field = {
            StepType.LLM_CALL: "llm_call",
            StepType.RETRIEVAL: "retrieval",
            StepType.TOOL_CALL: "tool_call",
            StepType.GUARD_DECISION: "guard_decision",
            StepType.APPROVAL: "approval",
            StepType.OUTPUT: "output",
            StepType.ERROR: "error",
        }
        expected_field = type_to_field[self.step_type]
        if getattr(self, expected_field) is None:
            raise ValueError(
                f"Step type is '{self.step_type.value}' but '{expected_field}' data is missing. "
                f"You must provide {expected_field} data for a {self.step_type.value} step."
            )
        return self


# ──────────────────────────────────────────────
# Trace — The complete recording of one AI interaction
# ──────────────────────────────────────────────


class Trace(BaseModel):
    """
    A complete trace of one AI agent interaction.

    This is like a movie — it has a start, a series of steps (scenes),
    and an end. Every time a customer sends a ticket, a new Trace is created.

    Example:
        trace = Trace(
            customer_id="cust_001",
            input_text="order 1042 ka refund de do",
            prompt_version="v3",
            model_version="gemini-2.0-flash",
        )
        trace.steps.append(TraceStep(...))
    """

    # Identity
    trace_id: str = Field(
        default_factory=lambda: f"tr-{uuid.uuid4().hex[:12]}",
        description="Unique trace ID, e.g. 'tr-a1b2c3d4e5f6'",
    )
    project_id: str = Field(default="default", description="Scoped enterprise project ID")

    # Context
    customer_id: str | None = Field(default=None, description="Customer who triggered this trace")
    session_id: str | None = Field(default=None, description="Session/conversation ID")
    input_text: str = Field(..., description="The original user input / ticket text")
    input_language: str | None = Field(
        default=None, description="Detected language: 'en', 'hi', 'hinglish'"
    )

    # Versioning — crucial for regression detection
    prompt_version: str = Field(..., description="Prompt template version, e.g. 'v3'")
    model_version: str = Field(..., description="Model name + version, e.g. 'gemini-2.0-flash'")

    # Steps (the scenes in our movie)
    steps: list[TraceStep] = Field(default_factory=list, description="Ordered list of trace steps")

    # Status & Timing
    status: TraceStatus = Field(default=TraceStatus.IN_PROGRESS)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = Field(default=None)

    # Aggregated metrics (computed after trace completes)
    total_tokens: int = Field(default=0, ge=0, description="Sum of all LLM call tokens")
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Sum of all step costs")
    total_latency_ms: float = Field(default=0.0, ge=0.0, description="End-to-end latency")
    step_count: int = Field(default=0, ge=0, description="Number of steps")

    # Metadata
    tags: list[str] = Field(default_factory=list, description="Tags for filtering, e.g. ['refund']")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_text")
    @classmethod
    def input_text_not_empty(cls, v: str) -> str:
        """Input text cannot be empty."""
        if not v.strip():
            raise ValueError("input_text cannot be empty or whitespace")
        return v

    @model_validator(mode="after")
    def validate_step_order(self) -> Trace:
        """Ensure steps are in correct order by step_index."""
        if self.steps:
            indices = [s.step_index for s in self.steps]
            if indices != sorted(indices):
                raise ValueError(f"Steps must be in order by step_index. Got: {indices}")
            # Check for duplicate step indices
            if len(indices) != len(set(indices)):
                raise ValueError(f"Duplicate step_index found in steps: {indices}")
        return self

    def compute_aggregates(self) -> None:
        """Recompute aggregate metrics from steps. Call after adding all steps."""
        self.step_count = len(self.steps)
        self.total_tokens = sum(
            s.llm_call.total_tokens for s in self.steps if s.llm_call is not None
        )
        self.total_cost_usd = sum(s.llm_call.cost_usd for s in self.steps if s.llm_call is not None)
        self.total_latency_ms = sum(s.duration_ms for s in self.steps if s.duration_ms is not None)

    def complete(self, status: TraceStatus = TraceStatus.COMPLETED) -> None:
        """Mark the trace as completed and compute aggregates."""
        self.status = status
        self.completed_at = datetime.now(UTC)
        self.compute_aggregates()

    def add_step(self, step: TraceStep) -> None:
        """Add a step to the trace, auto-setting step_index."""
        step.step_index = len(self.steps)
        self.steps.append(step)

    def get_steps_by_type(self, step_type: StepType) -> list[TraceStep]:
        """Get all steps of a specific type."""
        return [s for s in self.steps if s.step_type == step_type]

    def get_guard_decisions(self) -> list[GuardDecisionData]:
        """Get all guard decisions from this trace."""
        return [s.guard_decision for s in self.steps if s.guard_decision is not None]

    def get_tool_calls(self) -> list[ToolCallData]:
        """Get all tool calls from this trace."""
        return [s.tool_call for s in self.steps if s.tool_call is not None]

    def has_write_operations(self) -> bool:
        """Check if any tool call in this trace modified data."""
        return any(s.tool_call.is_write for s in self.steps if s.tool_call is not None)

    def was_blocked(self) -> bool:
        """Check if the trace was blocked by the guard."""
        return any(
            s.guard_decision.decision == GuardDecision.BLOCK
            for s in self.steps
            if s.guard_decision is not None
        )

    def needed_approval(self) -> bool:
        """Check if the trace required human approval."""
        return any(
            s.guard_decision.decision == GuardDecision.ASK_HUMAN
            for s in self.steps
            if s.guard_decision is not None
        )


# ──────────────────────────────────────────────
# ShopOps Workflow Definitions
# ──────────────────────────────────────────────


class WorkflowType(str, Enum):
    """The 6 workflows ShopOps AI can handle."""

    REFUND = "refund"
    CANCEL_ORDER = "cancel_order"
    CLOSE_TICKET = "close_ticket"
    UPDATE_INVENTORY = "update_inventory"
    CHANGE_SUBSCRIPTION = "change_subscription"
    BALANCE_QUERY = "balance_query"


class WorkflowDefinition(BaseModel):
    """Definition of a ShopOps workflow — what the AI can do."""

    workflow_type: WorkflowType
    description: str
    required_entities: list[str] = Field(
        description="Entities the AI must extract, e.g. ['order_id', 'reason']"
    )
    tools_used: list[str] = Field(
        description="Tools this workflow calls, e.g. ['issue_refund', 'update_inventory']"
    )
    requires_approval_above: float | None = Field(
        default=None, description="Amount threshold for human approval (in INR)"
    )
    is_reversible: bool = Field(default=True, description="Whether this action can be undone")
    risk_level: Severity = Field(default=Severity.LOW, description="Risk level of this workflow")


# ──────────────────────────────────────────────
# Pre-defined ShopOps Workflows
# ──────────────────────────────────────────────

SHOPOPS_WORKFLOWS: list[WorkflowDefinition] = [
    WorkflowDefinition(
        workflow_type=WorkflowType.REFUND,
        description="Process a refund for a customer order",
        required_entities=["order_id", "reason"],
        tools_used=["get_order", "check_refund_eligibility", "issue_refund", "update_inventory"],
        requires_approval_above=10000.0,  # ₹10K+ needs human approval
        is_reversible=False,
        risk_level=Severity.HIGH,
    ),
    WorkflowDefinition(
        workflow_type=WorkflowType.CANCEL_ORDER,
        description="Cancel a pending order before shipment",
        required_entities=["order_id", "reason"],
        tools_used=["get_order", "cancel_order", "process_refund"],
        requires_approval_above=20000.0,
        is_reversible=False,
        risk_level=Severity.HIGH,
    ),
    WorkflowDefinition(
        workflow_type=WorkflowType.CLOSE_TICKET,
        description="Close a support ticket after resolution",
        required_entities=["ticket_id", "resolution_summary"],
        tools_used=["get_ticket", "close_ticket"],
        requires_approval_above=None,  # No approval needed
        is_reversible=True,
        risk_level=Severity.LOW,
    ),
    WorkflowDefinition(
        workflow_type=WorkflowType.UPDATE_INVENTORY,
        description="Update inventory count for a product",
        required_entities=["product_id", "quantity_change", "reason"],
        tools_used=["get_inventory", "update_inventory"],
        requires_approval_above=None,
        is_reversible=True,
        risk_level=Severity.MEDIUM,
    ),
    WorkflowDefinition(
        workflow_type=WorkflowType.CHANGE_SUBSCRIPTION,
        description="Change or cancel a customer subscription",
        required_entities=["subscription_id", "action"],
        tools_used=["get_subscription", "update_subscription"],
        requires_approval_above=None,
        is_reversible=True,
        risk_level=Severity.MEDIUM,
    ),
    WorkflowDefinition(
        workflow_type=WorkflowType.BALANCE_QUERY,
        description="Check customer account balance or transaction history",
        required_entities=["customer_id"],
        tools_used=["get_balance", "get_transactions"],
        requires_approval_above=None,
        is_reversible=True,  # Read-only, always safe
        risk_level=Severity.LOW,
    ),
]
