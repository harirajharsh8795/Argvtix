"""
Rule 1: Duplicate Refund Detection
Finds orders where multiple refund transactions were issued.
Optimized to execute aggregation at the database layer.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from argvtix.db.models import Refund
from argvtix.trace.schemas import Severity
from argvtix.watchdog.rules.base import BaseWatchdogRule, WatchdogFinding


class DuplicateRefundRule(BaseWatchdogRule):
    """Detects multiple refund records issued for the same order."""

    @property
    def rule_name(self) -> str:
        return "duplicate_refund"

    @property
    def description(self) -> str:
        return "Detects multiple refunds issued for the same order"

    @property
    def severity(self) -> Severity:
        return Severity.HIGH

    def scan(self, db: Session) -> list[WatchdogFinding]:
        # Aggregate at the SQL layer: return only order_ids with > 1 refund
        duplicates = (
            db.query(
                Refund.order_id,
                func.count(Refund.id).label("refund_count"),
                func.sum(Refund.amount).label("total_refunded"),
            )
            .group_by(Refund.order_id)
            .having(func.count(Refund.id) > 1)
            .all()
        )

        if not duplicates:
            return []

        dup_order_ids = [d.order_id for d in duplicates]
        # Fetch only refund IDs for the offending orders in one targeted query
        all_dup_refunds = (
            db.query(Refund.id, Refund.order_id).filter(Refund.order_id.in_(dup_order_ids)).all()
        )
        refund_ids_by_order: dict[str, list[str]] = defaultdict(list)
        for r_id, o_id in all_dup_refunds:
            refund_ids_by_order[o_id].append(r_id)

        findings: list[WatchdogFinding] = []
        for row in duplicates:
            order_id = row.order_id
            total_refunded = float(row.total_refunded or 0.0)
            refund_ids = refund_ids_by_order.get(order_id, [])
            findings.append(
                WatchdogFinding(
                    rule_name=self.rule_name,
                    severity=self.severity,
                    description=(
                        f"Order {order_id[:8]} has {row.refund_count} separate refunds "
                        f"totaling ₹{total_refunded:,.2f}"
                    ),
                    entity_type="order",
                    entity_id=order_id,
                    details={
                        "refund_count": int(row.refund_count),
                        "total_refunded": total_refunded,
                        "refund_ids": refund_ids,
                    },
                )
            )
        return findings
