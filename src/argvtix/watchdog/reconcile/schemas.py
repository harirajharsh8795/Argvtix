"""
Reconciliation Data Schemas.

Defines the 4 canonical reconciliation failure modes across ERP, CRM, and agent DB:
1. DISCREPANCY_TOTAL_AMOUNT: DB order total != CRM invoice amount
2. ORPHAN_PAYMENT: Payment exists without corresponding valid order
3. MISSING_INVENTORY_DEDUCTION: Order placed/delivered but inventory count not decremented
4. STATUS_DESYNC: ERP status (e.g. shipped) != Agent DB status (e.g. cancelled)
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReconciliationFailureType(str, Enum):
    DISCREPANCY_TOTAL_AMOUNT = "discrepancy_total_amount"
    ORPHAN_PAYMENT = "orphan_payment"
    MISSING_INVENTORY_DEDUCTION = "missing_inventory_deduction"
    STATUS_DESYNC = "status_desync"


class ExternalEntityState(BaseModel):
    """External state representation from CRM, ERP, or payment gateway."""

    order_id: str
    crm_invoice_amount: float | None = None
    erp_order_status: str | None = None
    expected_inventory_deducted: int | None = None
    gateway_payment_id: str | None = None
    customer_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReconciliationItem(BaseModel):
    """A detected discrepancy between internal state and external ERP/CRM."""

    failure_type: ReconciliationFailureType
    entity_id: str
    entity_type: str  # "order" | "payment" | "inventory"
    expected_value: Any
    actual_value: Any
    discrepancy_details: str
    severity: str = "critical"  # "critical" | "warning" | "info"
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReconciliationResult(BaseModel):
    """Consolidated reconciliation audit report."""

    total_entities_checked: int
    total_discrepancies: int
    items: list[ReconciliationItem] = Field(default_factory=list)
    is_synchronized: bool = True
    audit_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
