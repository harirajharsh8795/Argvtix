"""
Action Guard Engine
Pre-execution policy enforcement and safety verification for AI agent actions.
Decides whether an action should be ALLOWed, BLOCKed, or sent for human approval (ASK_HUMAN).
"""

from datetime import UTC, datetime, timedelta
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from earp.db.models import Order, Payment, Refund
from earp.trace.schemas import GuardDecision, Severity


class GuardCheckRequest(BaseModel):
    """Request payload to evaluate an action proposal."""

    workflow_type: str = "refund"
    tool_name: str = "issue_refund"
    customer_id: str
    order_id: str
    amount: float = 0.0
    reason: str = ""
    metadata: dict = Field(default_factory=dict)


class GuardCheckResponse(BaseModel):
    """Result of policy guard evaluation."""

    decision: GuardDecision
    reason: str
    risk_level: Severity = Severity.LOW
    requires_human_approval: bool = False
    policy_rule_triggered: str | None = None


class ActionGuard:
    """Pre-action safety guardian."""

    REFUND_APPROVAL_THRESHOLD = 10000.0  # ₹10,000 threshold

    def evaluate(self, request: GuardCheckRequest, db: Session) -> GuardCheckResponse:
        """Evaluate action safety against database state and business policies."""
        # 0. Check negative amount
        if request.amount < 0:
            return GuardCheckResponse(
                decision=GuardDecision.BLOCK,
                reason=f"ACT-05: Refund amount cannot be negative ({request.amount}).",
                risk_level=Severity.HIGH,
                policy_rule_triggered="non_negative_amount",
            )

        # 1. Verify Order exists
        order = db.query(Order).filter_by(id=request.order_id).first()
        if not order:
            return GuardCheckResponse(
                decision=GuardDecision.BLOCK,
                reason=f"Order {request.order_id} does not exist.",
                risk_level=Severity.HIGH,
                policy_rule_triggered="verify_order_exists",
            )

        # 2. Verify Customer ownership
        if order.customer_id != request.customer_id:
            return GuardCheckResponse(
                decision=GuardDecision.BLOCK,
                reason=(
                    f"ACT-03: Customer ID mismatch: customer {request.customer_id} does not own order {request.order_id}."
                ),
                risk_level=Severity.CRITICAL,
                policy_rule_triggered="verify_customer_ownership",
            )

        # 3. Check order state preconditions (e.g. cancellation requires pending/processing)
        workflow = (request.workflow_type or "").lower()
        tool = (request.tool_name or "").lower()
        if "cancel" in workflow or "cancel" in tool:
            if (order.status or "").lower() not in ("pending", "processing"):
                return GuardCheckResponse(
                    decision=GuardDecision.BLOCK,
                    reason=(
                        f"ACT-04: Cannot cancel order in '{order.status}' status. Only pending or processing orders can be cancelled."
                    ),
                    risk_level=Severity.HIGH,
                    policy_rule_triggered="order_cancellable_state",
                )

        # 4. Check customer velocity (max 2 refunds per 60 minutes)
        if "refund" in workflow or "refund" in tool:
            cutoff_utc = datetime.now(UTC) - timedelta(minutes=60)
            cutoff_naive = (datetime.now(UTC) - timedelta(minutes=60)).replace(tzinfo=None)
            recent_refunds = (
                db.query(Refund)
                .filter(Refund.customer_id == request.customer_id)
                .all()
            )
            recent_count = 0
            for r in recent_refunds:
                if r.status in ("completed", "succeeded"):
                    r_dt = r.created_at
                    if r_dt is not None:
                        if r_dt.tzinfo is None:
                            if r_dt >= cutoff_naive:
                                recent_count += 1
                        else:
                            if r_dt >= cutoff_utc:
                                recent_count += 1
            if recent_count >= 2:
                return GuardCheckResponse(
                    decision=GuardDecision.ASK_HUMAN,
                    reason=(
                        f"ACT-06: Customer velocity limit reached ({recent_count} refunds in last 60m). Requires human verification."
                    ),
                    risk_level=Severity.HIGH,
                    requires_human_approval=True,
                    policy_rule_triggered="customer_velocity_cap",
                )

        # 5. Check for existing refunds (Prevent duplicate refunds)
        existing_refunds = (
            db.query(Refund)
            .filter(Refund.order_id == request.order_id)
            .filter(Refund.status.in_(["completed", "succeeded"]))
            .all()
        )
        if existing_refunds:
            prior_total = sum(r.amount for r in existing_refunds)
            return GuardCheckResponse(
                decision=GuardDecision.BLOCK,
                reason=(
                    f"ACT-02: Order {request.order_id} already has {len(existing_refunds)} refund(s) "
                    f"totaling ₹{prior_total:,.2f}. Duplicate refund prevented."
                ),
                risk_level=Severity.HIGH,
                policy_rule_triggered="prevent_duplicate_refund",
            )

        # 6. Check payment amount (Refund cannot exceed payment)
        payments = db.query(Payment).filter_by(order_id=request.order_id, status="succeeded").all()
        total_paid = sum(p.amount for p in payments)
        if request.amount > total_paid + 0.05:
            return GuardCheckResponse(
                decision=GuardDecision.BLOCK,
                reason=(
                    f"Proposed refund of ₹{request.amount:,.2f} exceeds total payments ₹{total_paid:,.2f}."
                ),
                risk_level=Severity.CRITICAL,
                policy_rule_triggered="cap_refund_at_payment",
            )

        # 7. Check monetary approval threshold (High-value transaction requires Human-in-the-Loop)
        if request.amount >= self.REFUND_APPROVAL_THRESHOLD:
            return GuardCheckResponse(
                decision=GuardDecision.ASK_HUMAN,
                reason=(
                    f"ACT-01: Refund amount ₹{request.amount:,.2f} meets or exceeds threshold "
                    f"₹{self.REFUND_APPROVAL_THRESHOLD:,.2f}. Queued for human approval."
                ),
                risk_level=Severity.HIGH,
                requires_human_approval=True,
                policy_rule_triggered="human_approval_over_threshold",
            )

        # All checks passed cleanly
        return GuardCheckResponse(
            decision=GuardDecision.ALLOW,
            reason="All security and policy checks passed. Action approved for execution.",
            risk_level=Severity.LOW,
            requires_human_approval=False,
        )
