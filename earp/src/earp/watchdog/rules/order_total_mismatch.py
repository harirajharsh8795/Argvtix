"""
Rule 2: Order Total Mismatch Detection
Validates that sum of order item subtotals + tax equals order total_amount.
Optimized to eliminate N+1 queries using a single database subquery join.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from earp.db.models import Order, OrderItem
from earp.trace.schemas import Severity
from earp.watchdog.rules.base import BaseWatchdogRule, WatchdogFinding


class OrderTotalMismatchRule(BaseWatchdogRule):
    """Detects discrepancies between item totals, calculated tax, and recorded order total."""

    @property
    def rule_name(self) -> str:
        return "order_total_mismatch"

    @property
    def description(self) -> str:
        return "Validates that item subtotal + tax equals total_amount on orders"

    @property
    def severity(self) -> Severity:
        return Severity.MEDIUM

    def scan(self, db: Session) -> list[WatchdogFinding]:
        # Pre-aggregate item subtotals by order_id in SQL to eliminate N+1 loops
        item_subtotals = (
            db.query(
                OrderItem.order_id,
                func.coalesce(func.sum(OrderItem.line_total), 0.0).label("calculated_subtotal"),
            )
            .group_by(OrderItem.order_id)
            .subquery()
        )

        orders_with_calc = (
            db.query(
                Order.id,
                Order.tax,
                Order.total_amount,
                func.coalesce(item_subtotals.c.calculated_subtotal, 0.0).label("subtotal"),
            )
            .outerjoin(item_subtotals, Order.id == item_subtotals.c.order_id)
            .all()
        )

        findings: list[WatchdogFinding] = []
        for row in orders_with_calc:
            calculated_subtotal = float(row.subtotal)
            tax = float(row.tax or 0.0)
            total_amount = float(row.total_amount or 0.0)
            calculated_total = round(calculated_subtotal + tax, 2)

            # Check if discrepancy exceeds 0.05 currency unit
            diff = abs(total_amount - calculated_total)
            if diff > 0.05:
                order_id = row.id
                findings.append(
                    WatchdogFinding(
                        rule_name=self.rule_name,
                        severity=self.severity,
                        description=(
                            f"Order {order_id[:8]} total mismatch: recorded ₹{total_amount:,.2f} "
                            f"vs calculated ₹{calculated_total:,.2f} (diff: ₹{diff:,.2f})"
                        ),
                        entity_type="order",
                        entity_id=order_id,
                        details={
                            "recorded_total": total_amount,
                            "calculated_total": calculated_total,
                            "discrepancy": diff,
                        },
                    )
                )
        return findings
