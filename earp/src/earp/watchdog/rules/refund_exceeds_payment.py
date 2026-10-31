"""
Rule 3: Refund Exceeds Payment Amount Detection
Detects orders where cumulative refunds exceed the total amount paid by the customer.
Optimized to execute aggregation and excess filtering at the database layer.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from earp.db.models import Payment, Refund
from earp.trace.schemas import Severity
from earp.watchdog.rules.base import BaseWatchdogRule, WatchdogFinding


class RefundExceedsPaymentRule(BaseWatchdogRule):
    """Detects when total refunded amount exceeds total customer payments for an order."""

    @property
    def rule_name(self) -> str:
        return "refund_exceeds_payment"

    @property
    def description(self) -> str:
        return "Detects when total refunded amount exceeds total customer payments"

    @property
    def severity(self) -> Severity:
        return Severity.CRITICAL

    def scan(self, db: Session) -> list[WatchdogFinding]:
        # 1. Total paid per order (succeeded or refunded)
        paid_subq = (
            db.query(
                Payment.order_id,
                func.sum(Payment.amount).label("total_paid"),
            )
            .filter(Payment.status.in_(["succeeded", "refunded"]))
            .group_by(Payment.order_id)
            .subquery()
        )

        # 2. Total refunded per order (completed refunds)
        refund_subq = (
            db.query(
                Refund.order_id,
                func.sum(Refund.amount).label("total_refunded"),
            )
            .filter(Refund.status == "completed")
            .group_by(Refund.order_id)
            .subquery()
        )

        # 3. Join in database and filter where total_refunded > total_paid + 0.05
        excess_orders = (
            db.query(
                refund_subq.c.order_id,
                func.coalesce(paid_subq.c.total_paid, 0.0).label("total_paid"),
                refund_subq.c.total_refunded,
            )
            .outerjoin(paid_subq, refund_subq.c.order_id == paid_subq.c.order_id)
            .filter(refund_subq.c.total_refunded > func.coalesce(paid_subq.c.total_paid, 0.0) + 0.05)
            .all()
        )

        findings: list[WatchdogFinding] = []
        for row in excess_orders:
            order_id = row.order_id
            total_paid = float(row.total_paid)
            total_refunded = float(row.total_refunded)
            excess = total_refunded - total_paid

            findings.append(
                WatchdogFinding(
                    rule_name=self.rule_name,
                    severity=self.severity,
                    description=(
                        f"Order {order_id[:8]} refunded amount ₹{total_refunded:,.2f} "
                        f"exceeds total paid ₹{total_paid:,.2f} by ₹{excess:,.2f}"
                    ),
                    entity_type="order",
                    entity_id=order_id,
                    details={
                        "total_paid": total_paid,
                        "total_refunded": total_refunded,
                        "excess_amount": excess,
                    },
                )
            )
        return findings
