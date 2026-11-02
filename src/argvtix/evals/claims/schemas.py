"""
Claim-vs-State Schemas.

Pydantic data models for structured claim extraction, entity state snapshots,
ground-truth evidence bundles, and deterministic verification verdicts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ClaimType(str, Enum):
    """Category of factual claim asserted in agent natural language output."""

    STATUS_UPDATE = "status_update"  # e.g., "Your order has been shipped"
    REFUND_ISSUED = "refund_issued"  # e.g., "Refund of Rs 500 has been issued"
    PAYMENT_PROCESSED = "payment_processed"  # e.g., "Payment has been processed"
    ORDER_CANCELLED = "order_cancelled"  # e.g., "Order ORD-1042 has been cancelled"
    TICKET_ESCALATED = "ticket_escalated"  # e.g., "Ticket escalated to Tier 2 support"
    INVENTORY_MODIFIED = "inventory_modified"  # e.g., "Item marked as out of stock"
    ACTION_TAKEN = "action_taken"  # e.g., "Appointment scheduled for Monday"
    POLICY_STATED = "policy_stated"  # e.g., "Refund policy window is 7 days"


class ClaimVerdict(str, Enum):
    """
    Verification outcome when comparing extracted claim to ground truth DB/tool state.
    Covers the 6 blueprint-mandated failure categories plus verified and unverifiable states.
    """

    VERIFIED = "verified"  # Claim matches actual tool/DB state
    FALSE_SUCCESS = "false_success"  # Tool failed/error/no DB write, but agent claimed success
    FALSE_FAILURE = "false_failure"  # Tool succeeded, but agent claimed failure/inability
    OMITTED_FAILURE = "omitted_failure"  # Tool failed, but agent omitted any failure mention
    WRONG_ENTITY = "wrong_entity"  # Agent claimed action on entity X, but tool affected entity Y
    PARTIAL_SUCCESS = (
        "partial_success"  # Agent claimed full action/amount, but tool executed partial
    )
    STATUS_MISMATCH = "status_mismatch"  # Agent claimed status A, but DB shows status B
    UNVERIFIABLE = "unverifiable"  # No tool execution or DB state available to verify


class ClaimSeverity(str, Enum):
    """Severity of a discrepancy or hallucination."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Claim(BaseModel):
    """
    Structured factual claim extracted from agent response text.
    """

    claim_id: str = Field(default_factory=lambda: f"claim_{uuid.uuid4().hex[:8]}")
    source_text: str = Field(..., description="Exact sentence or clause from agent response")
    claim_type: ClaimType = Field(..., description="Taxonomy classification of the claim")
    entity_type: str = Field(
        ..., description="Target domain entity: order, refund, ticket, account, etc."
    )
    entity_id: str | None = Field(
        default=None, description="Extracted entity identifier (e.g. ORD-1042)"
    )
    claimed_status: str | None = Field(
        default=None, description="Reported state: completed, cancelled, etc."
    )
    claimed_amount: float | None = Field(
        default=None, description="Numerical amount if financial/numeric claim"
    )
    claimed_currency: str | None = Field(
        default=None, description="Currency code (e.g. INR, USD) if present"
    )
    is_success_claimed: bool = Field(
        default=True,
        description="True if agent asserts the requested action succeeded or is complete",
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Extraction confidence score"
    )

    @field_validator("claimed_amount", mode="before")
    @classmethod
    def parse_float_amount(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            clean = (
                v.replace(",", "")
                .replace("$", "")
                .replace("₹", "")
                .replace("Rs.", "")
                .replace("Rs", "")
                .strip()
            )
            try:
                return float(clean)
            except ValueError:
                return None
        return None


class EntityStateSnapshot(BaseModel):
    """
    Ground truth state snapshot captured directly from tool execution results
    or database rows written during the interaction.
    """

    entity_id: str = Field(..., description="Identifier of the entity affected or checked")
    entity_type: str = Field(..., description="Entity type: order, refund, ticket, payment, etc.")
    tool_name: str | None = Field(
        default=None, description="Name of tool that operated on this entity"
    )
    tool_status: str = Field(
        default="success",
        description="Execution status: 'success', 'error', 'failed', 'blocked'",
    )
    tool_error: str | None = Field(
        default=None, description="Error message if tool execution failed"
    )
    actual_status: str | None = Field(
        default=None, description="State in database after tool execution"
    )
    actual_amount: float | None = Field(
        default=None, description="Actual amount written or verified in DB"
    )
    actual_currency: str | None = Field(default="INR", description="Currency of actual amount")
    rows_affected: int = Field(
        default=1, ge=0, description="Number of database rows inserted or updated"
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Underlying DB record or tool payload"
    )


class EvidenceBundle(BaseModel):
    """
    Complete bundle of ground truth evidence and agent output for a verification run.
    """

    agent_response_text: str = Field(..., description="Full text returned by the AI agent")
    claims: list[Claim] = Field(
        default_factory=list, description="Extracted claims to be evaluated"
    )
    snapshots: list[EntityStateSnapshot] = Field(
        default_factory=list,
        description="DB/tool snapshots representing true system state",
    )
    tool_records: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Raw tool call logs from trace execution",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimVerificationResult(BaseModel):
    """
    Verdict and discrepancy report for an individual claim.
    """

    claim_id: str
    claim: Claim
    verdict: ClaimVerdict
    severity: ClaimSeverity
    explanation: str
    matched_snapshot: EntityStateSnapshot | None = None
    expected_state: str | None = None
    actual_state: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExtractionAccuracyReport(BaseModel):
    """
    Evaluation metrics specifically measuring Claim Extractor performance
    against human-labelled ground truth claims.
    """

    total_expected_claims: int = 0
    total_extracted_claims: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0


class ClaimsEvaluationReport(BaseModel):
    """
    Consolidated report summarizing Claim-vs-State verification across an interaction.
    """

    total_claims: int
    verified_count: int
    violations_count: int
    accuracy_percent: float
    verdict_counts: dict[str, int] = Field(default_factory=dict)
    results: list[ClaimVerificationResult] = Field(default_factory=list)
    extraction_report: ExtractionAccuracyReport | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
