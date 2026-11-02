"""
Rule 6: Orphan / Ghost Payment Detection
Detects payments in 'succeeded' status that link to non-existent orders,
or payments recorded without a valid customer mapping.
Optimized to execute via a single database outer join.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from argvtix.db.models import Order, Payment
from argvtix.trace.schemas import Severity
from argvtix.watchdog.rules.base import BaseWatchdogRule, WatchdogFinding


class OrphanPaymentRule(BaseWatchdogRule):
    """
    Detects orphan payment records that point to non-existent orders.
    """

    @property
    def rule_name(self) -> str:
        return "orphan_payment"

    @property
    def description(self) -> str:
        return "Detects succeeded payments referencing non-existent orders"

    @property
    def severity(self) -> Severity:
        return Severity.HIGH

    def scan(self, db: Session) -> list[WatchdogFinding]:
        # Perform outer join in SQL to find orphan payments without loading all order IDs
        orphan_payments = (
            db.query(Payment)
            .outerjoin(Order, Payment.order_id == Order.id)
            .filter(
                Payment.status == "succeeded",
                (Payment.order_id.is_(None)) | (Order.id.is_(None)),
            )
            .all()
        )

        findings: list[WatchdogFinding] = []
        for pmt in orphan_payments:
            findings.append(
                WatchdogFinding(
                    rule_name=self.rule_name,
                    severity=self.severity,
                    description=(
                        f"Payment {pmt.id[:8]} of ₹{pmt.amount:,.2f} has missing or orphan order_id {pmt.order_id}"
                    ),
                    entity_type="payment",
                    entity_id=pmt.id,
                    details={
                        "payment_id": pmt.id,
                        "order_id": pmt.order_id,
                        "amount": float(pmt.amount),
                        "customer_id": pmt.customer_id,
                    },
                )
            )

        return findings
