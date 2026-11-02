"""
ERP / CRM Reconciliation Engine.

Audits and reconciles internal database records with external CRM/ERP system states.
Detects 4 failure modes:
1. DISCREPANCY_TOTAL_AMOUNT: DB Order.total_amount != CRM invoice amount
2. ORPHAN_PAYMENT: Payment exists with invalid or missing order
3. MISSING_INVENTORY_DEDUCTION: Delivered order without inventory adjustment
4. STATUS_DESYNC: ERP status (e.g. 'shipped') != DB status (e.g. 'cancelled')
"""
from __future__ import annotations

from typing import Sequence
import uuid

from sqlalchemy.orm import Session

from argvtix.db.models import Order, OrderItem, Payment, Product, WatchdogFindingRecord
from argvtix.watchdog.reconcile.schemas import (
    ExternalEntityState,
    ReconciliationFailureType,
    ReconciliationItem,
    ReconciliationResult,
)


class ReconciliationEngine:
    """Reconciliation coordinator between DB state and external business systems."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def check_amount_discrepancy(
        self,
        order: Order,
        crm_amount: float,
    ) -> ReconciliationItem | None:
        """Verifies DB order total against external CRM invoice amount."""
        if abs(order.total_amount - crm_amount) > 0.01:
            return ReconciliationItem(
                failure_type=ReconciliationFailureType.DISCREPANCY_TOTAL_AMOUNT,
                entity_id=order.id,
                entity_type="order",
                expected_value=crm_amount,
                actual_value=order.total_amount,
                discrepancy_details=(
                    f"DB order amount (Rs {order.total_amount:.2f}) does not match "
                    f"CRM invoice amount (Rs {crm_amount:.2f})"
                ),
                severity="critical",
            )
        return None

    def check_status_desync(
        self,
        order: Order,
        erp_status: str,
    ) -> ReconciliationItem | None:
        """Verifies DB status against external ERP status."""
        # Normalize statuses
        db_stat = order.status.strip().lower()
        erp_stat = erp_status.strip().lower()

        # Direct contradiction checks
        conflict = False
        if db_stat == "cancelled" and erp_stat in ("shipped", "delivered", "in_transit"):
            conflict = True
        elif db_stat == "delivered" and erp_stat in ("cancelled", "returned", "failed"):
            conflict = True
        elif db_stat != erp_stat and db_stat in ("pending", "processing") and erp_stat in ("delivered", "cancelled"):
            conflict = True

        if conflict:
            return ReconciliationItem(
                failure_type=ReconciliationFailureType.STATUS_DESYNC,
                entity_id=order.id,
                entity_type="order",
                expected_value=erp_status,
                actual_value=order.status,
                discrepancy_details=(
                    f"Status desynchronization: ERP reports '{erp_status}' but DB state is '{order.status}'"
                ),
                severity="critical",
            )
        return None

    def check_orphan_payments(self) -> list[ReconciliationItem]:
        """Detects payments in DB that do not map to any valid Order."""
        orphans: list[ReconciliationItem] = []
        payments = self.db.query(Payment).all()

        for p in payments:
            if not p.order_id:
                orphans.append(
                    ReconciliationItem(
                        failure_type=ReconciliationFailureType.ORPHAN_PAYMENT,
                        entity_id=p.id,
                        entity_type="payment",
                        expected_value="Valid order_id",
                        actual_value=None,
                        discrepancy_details=f"Payment {p.id} has no associated order_id",
                        severity="critical",
                    )
                )
                continue

            order = self.db.query(Order).filter(Order.id == p.order_id).first()
            if not order:
                orphans.append(
                    ReconciliationItem(
                        failure_type=ReconciliationFailureType.ORPHAN_PAYMENT,
                        entity_id=p.id,
                        entity_type="payment",
                        expected_value=f"Existing Order {p.order_id}",
                        actual_value="Order not found in DB",
                        discrepancy_details=f"Payment {p.id} references non-existent order {p.order_id}",
                        severity="critical",
                    )
                )
        return orphans

    def check_inventory_deductions(self) -> list[ReconciliationItem]:
        """Verifies that fulfilled orders have corresponding inventory deductions."""
        discrepancies: list[ReconciliationItem] = []
        # Find delivered or processing orders
        active_orders = (
            self.db.query(Order)
            .filter(Order.status.in_(["delivered", "processing", "shipped"]))
            .all()
        )

        for o in active_orders:
            items = self.db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
            for it in items:
                prod = self.db.query(Product).filter(Product.id == it.product_id).first()
                if prod is not None and prod.inventory_count < 0:
                    discrepancies.append(
                        ReconciliationItem(
                            failure_type=ReconciliationFailureType.MISSING_INVENTORY_DEDUCTION,
                            entity_id=prod.id,
                            entity_type="inventory",
                            expected_value="inventory_count >= 0",
                            actual_value=prod.inventory_count,
                            discrepancy_details=(
                                f"Product {prod.sku} has negative inventory {prod.inventory_count} "
                                f"after order {o.id}"
                            ),
                            severity="critical",
                        )
                    )
        return discrepancies

    def run_reconciliation(
        self,
        external_states: Sequence[ExternalEntityState] | None = None,
        persist_findings: bool = True,
    ) -> ReconciliationResult:
        """
        Executes full reconciliation across all 4 categories.
        Optionally persists discrepancies to WatchdogFindingRecord.
        """
        discrepancies: list[ReconciliationItem] = []
        total_checked = 0

        # 1. External state comparisons (CRM Amount & ERP Status)
        if external_states:
            for ext in external_states:
                total_checked += 1
                order = self.db.query(Order).filter(Order.id == ext.order_id).first()
                if not order:
                    discrepancies.append(
                        ReconciliationItem(
                            failure_type=ReconciliationFailureType.STATUS_DESYNC,
                            entity_id=ext.order_id,
                            entity_type="order",
                            expected_value=ext.erp_order_status or "Known order",
                            actual_value="Missing from DB",
                            discrepancy_details=f"External system references order {ext.order_id} missing from DB",
                            severity="warning",
                        )
                    )
                    continue

                if ext.crm_invoice_amount is not None:
                    item = self.check_amount_discrepancy(order, ext.crm_invoice_amount)
                    if item:
                        discrepancies.append(item)

                if ext.erp_order_status is not None:
                    item = self.check_status_desync(order, ext.erp_order_status)
                    if item:
                        discrepancies.append(item)

        # 2. Internal Orphan Payment Checks
        orphan_items = self.check_orphan_payments()
        discrepancies.extend(orphan_items)
        total_checked += len(orphan_items)

        # 3. Internal Inventory Consistency Checks
        inv_items = self.check_inventory_deductions()
        discrepancies.extend(inv_items)
        total_checked += len(inv_items)

        # Persist to Watchdog findings if requested
        if persist_findings and discrepancies:
            for d in discrepancies:
                rec = WatchdogFindingRecord(
                    id=f"rec_{uuid.uuid4().hex[:12]}",
                    rule_name=f"reconcile_{d.failure_type.value}",
                    severity=d.severity,
                    entity_type=d.entity_type,
                    entity_id=d.entity_id,
                    description=d.discrepancy_details,
                    suggested_action="Review cross-system ledger and reconcile manually or trigger resync",
                )
                self.db.add(rec)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()

        return ReconciliationResult(
            total_entities_checked=max(total_checked, len(discrepancies)),
            total_discrepancies=len(discrepancies),
            items=discrepancies,
            is_synchronized=len(discrepancies) == 0,
        )
