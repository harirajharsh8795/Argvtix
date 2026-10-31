"""
Human-in-the-Loop Approval Queue.

Manages high-risk action proposals flagged by ActionGuard (ASK_HUMAN).
Provides state machine for approval workflows:
- PENDING -> APPROVED (triggers execution through ToolGateway)
- PENDING -> REJECTED (halts execution, informs agent/customer)
- PENDING -> EDITED (executes with modified human-verified parameters)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from earp.db.models import ApprovalQueueRecord
from earp.trace.schemas import ApprovalStatus, Severity


class ApprovalItemResponse(BaseModel):
    """API view of an approval queue item."""

    id: str
    action_type: str
    tool_name: str
    entity_id: str
    customer_id: str | None = None
    amount: float | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    guard_reasons: str | None = None
    risk_level: str = "high"
    reviewer_id: str | None = None
    reviewer_notes: str | None = None
    edited_payload: dict[str, Any] | None = None
    idempotency_key: str | None = None
    created_at: str
    decided_at: str | None = None


class ApprovalDecisionRequest(BaseModel):
    """Request to approve or reject a pending action."""

    reviewer_id: str = "human_reviewer"
    notes: str = ""


class ApprovalEditRequest(BaseModel):
    """Request to edit parameters and approve an action."""

    reviewer_id: str = "human_reviewer"
    notes: str = ""
    edited_payload: dict[str, Any]


class ApprovalQueue:
    """Operations on the human-in-the-loop approval queue."""

    def enqueue(
        self,
        action_type: str,
        tool_name: str,
        entity_id: str,
        payload: dict[str, Any],
        customer_id: str | None = None,
        amount: float | None = None,
        guard_reason: str = "",
        risk_level: Severity = Severity.HIGH,
        idempotency_key: str | None = None,
        db: Session | None = None,
    ) -> ApprovalQueueRecord:
        """Create a new pending approval item in the database."""
        if db is None:
            raise ValueError("Database session is required to enqueue approval.")

        record = ApprovalQueueRecord(
            action_type=action_type,
            tool_name=tool_name,
            entity_id=str(entity_id),
            customer_id=str(customer_id) if customer_id else None,
            amount=amount,
            payload_json=json.dumps(payload),
            status=ApprovalStatus.PENDING.value,
            guard_reasons=guard_reason,
            risk_level=risk_level.value if hasattr(risk_level, "value") else str(risk_level),
            idempotency_key=idempotency_key,
            created_at=datetime.now(UTC),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_pending(
        self,
        db: Session,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalQueueRecord]:
        """List all pending items awaiting human review."""
        return (
            db.query(ApprovalQueueRecord)
            .filter_by(status=ApprovalStatus.PENDING.value)
            .order_by(ApprovalQueueRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_all(
        self,
        db: Session,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalQueueRecord]:
        """List items filtered by status."""
        q = db.query(ApprovalQueueRecord)
        if status:
            q = q.filter_by(status=status)
        return q.order_by(ApprovalQueueRecord.created_at.desc()).offset(offset).limit(limit).all()

    def get_by_id(self, approval_id: str, db: Session) -> ApprovalQueueRecord | None:
        """Fetch single approval record."""
        return db.query(ApprovalQueueRecord).filter_by(id=approval_id).first()

    def approve(
        self,
        approval_id: str,
        reviewer_id: str,
        notes: str,
        db: Session,
        gateway: Any | None = None,
    ) -> tuple[ApprovalQueueRecord, Any]:
        """
        Human approves the action.
        Status changes to APPROVED, and if gateway provided, executes tool.
        """
        record = self.get_by_id(approval_id, db)
        if not record:
            raise ValueError(f"Approval request {approval_id} not found.")

        if record.status != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval request {approval_id} already decided (status: {record.status}).")

        record.status = ApprovalStatus.APPROVED.value
        record.reviewer_id = reviewer_id
        record.reviewer_notes = notes
        record.decided_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)

        execution_result = None
        if gateway is not None:
            payload = json.loads(record.payload_json)
            execution_result = gateway.execute_bypassing_guard(
                tool_name=record.tool_name,
                params=payload,
                db=db,
            )

        return record, execution_result

    def reject(
        self,
        approval_id: str,
        reviewer_id: str,
        reason: str,
        db: Session,
    ) -> ApprovalQueueRecord:
        """Human rejects the action."""
        record = self.get_by_id(approval_id, db)
        if not record:
            raise ValueError(f"Approval request {approval_id} not found.")

        if record.status != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval request {approval_id} already decided (status: {record.status}).")

        record.status = ApprovalStatus.REJECTED.value
        record.reviewer_id = reviewer_id
        record.reviewer_notes = reason
        record.decided_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)
        return record

    def edit_and_approve(
        self,
        approval_id: str,
        edited_payload: dict[str, Any],
        reviewer_id: str,
        notes: str,
        db: Session,
        gateway: Any | None = None,
    ) -> tuple[ApprovalQueueRecord, Any]:
        """Human modifies parameters (e.g. lowering refund amount) and approves."""
        record = self.get_by_id(approval_id, db)
        if not record:
            raise ValueError(f"Approval request {approval_id} not found.")

        if record.status != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval request {approval_id} already decided (status: {record.status}).")

        record.status = ApprovalStatus.EDITED.value
        record.reviewer_id = reviewer_id
        record.reviewer_notes = notes
        record.edited_payload_json = json.dumps(edited_payload)
        record.decided_at = datetime.now(UTC)
        db.commit()
        db.refresh(record)

        execution_result = None
        if gateway is not None:
            execution_result = gateway.execute_bypassing_guard(
                tool_name=record.tool_name,
                params=edited_payload,
                db=db,
            )

        return record, execution_result
