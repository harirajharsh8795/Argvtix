"""
Rule 4: Inventory Discrepancy Detection
Checks whether completed orders have appropriate inventory deduction audit logs.
Optimized to eliminate N+1 queries using database-level aggregation joins.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from argvtix.db.models import InventoryLog, Order, OrderItem
from argvtix.trace.schemas import Severity
from argvtix.watchdog.rules.base import BaseWatchdogRule, WatchdogFinding


class InventoryDiscrepancyRule(BaseWatchdogRule):
    """Detects completed orders that lack inventory deduction records."""

    @property
    def rule_name(self) -> str:
        return "inventory_discrepancy"

    @property
    def description(self) -> str:
        return "Detects completed orders with missing inventory deduction logs"

    @property
    def severity(self) -> Severity:
        return Severity.HIGH

    def scan(self, db: Session) -> list[WatchdogFinding]:
        # 1. Count items per order in database
        items_count_subq = (
            db.query(OrderItem.order_id, func.count(OrderItem.id).label("item_count"))
            .group_by(OrderItem.order_id)
            .subquery()
        )

        # 2. Count inventory deduction logs per order in database
        logs_count_subq = (
            db.query(InventoryLog.order_id, func.count(InventoryLog.id).label("log_count"))
            .filter(InventoryLog.reason == "order_placed", InventoryLog.order_id.isnot(None))
            .group_by(InventoryLog.order_id)
            .subquery()
        )

        # 3. Join on completed orders and filter where expected > 0 and logged == 0
        discrepant_orders = (
            db.query(
                Order.id,
                func.coalesce(items_count_subq.c.item_count, 0).label("expected_items"),
                func.coalesce(logs_count_subq.c.log_count, 0).label("logged_count"),
            )
            .filter(Order.status == "completed")
            .outerjoin(items_count_subq, Order.id == items_count_subq.c.order_id)
            .outerjoin(logs_count_subq, Order.id == logs_count_subq.c.order_id)
            .filter(
                func.coalesce(items_count_subq.c.item_count, 0) > 0,
                func.coalesce(logs_count_subq.c.log_count, 0) == 0,
            )
            .all()
        )

        findings: list[WatchdogFinding] = []
        for row in discrepant_orders:
            order_id = row.id
            expected_items_count = int(row.expected_items)
            logged_count = int(row.logged_count)

            findings.append(
                WatchdogFinding(
                    rule_name=self.rule_name,
                    severity=self.severity,
                    description=(
                        f"Order {order_id[:8]} completed with {expected_items_count} items "
                        "but has no corresponding inventory deduction logs"
                    ),
                    entity_type="order",
                    entity_id=order_id,
                    details={
                        "expected_items": expected_items_count,
                        "inventory_logs_found": logged_count,
                    },
                )
            )
        return findings
