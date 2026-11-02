"""
SQLAlchemy ORM Models for ARGVTIX.
Includes:
- 8 Core Business Tables (Customers, Products, Orders, Items, Payments, Refunds, Inventory, Tickets)
- Observability & Reliability Tables (Traces, Steps, Watchdog Findings, Approval Queue)
- Optimized Single-Column and Composite Database Indexes for Production Latency
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from argvtix.db.session import Base


def generate_uuid() -> str:
    """Generate string UUID."""
    return str(uuid.uuid4())


# ============================================================================
# Business Domain Tables (ShopOps)
# ============================================================================


class Customer(Base):
    """Customer profile entity."""

    __tablename__ = "customers"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(32), nullable=True)
    tier = Column(String(32), default="standard")  # standard, silver, gold, platinum
    wallet_balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    orders = relationship("Order", back_populates="customer")
    payments = relationship("Payment", back_populates="customer")
    refunds = relationship("Refund", back_populates="customer")
    tickets = relationship("SupportTicket", back_populates="customer")
    ledger_entries = relationship("LedgerEntry", back_populates="customer")


class Product(Base):
    """Catalog product with real-time inventory count."""

    __tablename__ = "products"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    sku = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    inventory_count = Column(Integer, default=0, nullable=False)
    category = Column(String(64), default="general", index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    order_items = relationship("OrderItem", back_populates="product")
    inventory_logs = relationship("InventoryLog", back_populates="product")


class Order(Base):
    """Customer sales order."""

    __tablename__ = "orders"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    status = Column(
        String(32), default="pending", nullable=False, index=True
    )  # pending, completed, cancelled, refunded
    subtotal = Column(Float, default=0.0, nullable=False)
    tax = Column(Float, default=0.0, nullable=False)
    total_amount = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")
    refunds = relationship("Refund", back_populates="order")
    tickets = relationship("SupportTicket", back_populates="order")

    __table_args__ = (
        Index("ix_orders_customer_created", "customer_id", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
    )


class OrderItem(Base):
    """Line item in a customer order."""

    __tablename__ = "order_items"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    order_id = Column(String(64), ForeignKey("orders.id"), nullable=False, index=True)
    product_id = Column(String(64), ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Float, nullable=False)
    line_total = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class Payment(Base):
    """Payment transaction received for an order."""

    __tablename__ = "payments"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    order_id = Column(String(64), ForeignKey("orders.id"), nullable=False, index=True)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(
        String(32), default="succeeded", nullable=False, index=True
    )  # succeeded, failed, refunded
    method = Column(String(32), default="credit_card")  # upi, credit_card, netbanking, cod
    transaction_ref = Column(String(128), unique=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    order = relationship("Order", back_populates="payments")
    customer = relationship("Customer", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment")

    __table_args__ = (
        Index("ix_payments_order_status", "order_id", "status"),
        Index("ix_payments_customer_created", "customer_id", "created_at"),
    )


class Refund(Base):
    """Refund issued back to customer for an order/payment."""

    __tablename__ = "refunds"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    order_id = Column(String(64), ForeignKey("orders.id"), nullable=False, index=True)
    payment_id = Column(String(64), ForeignKey("payments.id"), nullable=True, index=True)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(String(255), nullable=True)
    status = Column(
        String(32), default="completed", nullable=False, index=True
    )  # pending, completed, rejected
    processed_by = Column(String(64), default="system")  # ai_agent, human_agent, system
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    order = relationship("Order", back_populates="refunds")
    payment = relationship("Payment", back_populates="refunds")
    customer = relationship("Customer", back_populates="refunds")

    __table_args__ = (
        Index("ix_refunds_order_status", "order_id", "status"),
        Index("ix_refunds_customer_created", "customer_id", "created_at"),
    )


class InventoryLog(Base):
    """Audit ledger of all stock additions/deductions."""

    __tablename__ = "inventory_logs"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    product_id = Column(String(64), ForeignKey("products.id"), nullable=False, index=True)
    change_amount = Column(
        Integer, nullable=False
    )  # negative for sales, positive for restock/return
    reason = Column(
        String(128), nullable=False, index=True
    )  # order_placed, order_cancelled, return_restock, manual_audit
    order_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    product = relationship("Product", back_populates="inventory_logs")


class SupportTicket(Base):
    """Customer support interaction ticket."""

    __tablename__ = "support_tickets"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    order_id = Column(String(64), ForeignKey("orders.id"), nullable=True, index=True)
    subject = Column(String(255), nullable=False)
    issue_description = Column(Text, nullable=False)
    status = Column(String(32), default="open", index=True)  # open, in_progress, resolved, closed
    priority = Column(String(32), default="medium", index=True)  # low, medium, high, urgent
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    customer = relationship("Customer", back_populates="tickets")
    order = relationship("Order", back_populates="tickets")

    __table_args__ = (Index("ix_support_tickets_status_priority", "status", "priority"),)


class LedgerEntry(Base):
    """Financial ledger tracking debits and credits for customer wallets."""

    __tablename__ = "ledger_entries"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    entry_type = Column(String(32), nullable=False, index=True)  # credit | debit
    amount = Column(Float, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    customer = relationship("Customer", back_populates="ledger_entries")

    __table_args__ = (Index("ix_ledger_customer_type", "customer_id", "entry_type"),)


# ============================================================================
# Observability & Reliability Tables (ARGVTIX Platform)
# ============================================================================


class TraceRecord(Base):
    """Persisted AI execution trace."""

    __tablename__ = "traces"

    id = Column(String(64), primary_key=True)  # trace_id
    project_id = Column(String(64), nullable=False, default="default", index=True)
    session_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    channel = Column(String(32), default="web")
    workflow_type = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="in_progress", index=True)
    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    total_latency_ms = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    total_tokens = Column(Integer, default=0)
    tags_json = Column(Text, nullable=True)  # JSON-encoded string
    metadata_json = Column(Text, nullable=True)  # JSON-encoded string
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    completed_at = Column(DateTime, nullable=True)

    steps = relationship("TraceStepRecord", back_populates="trace", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_traces_workflow_created", "workflow_type", "created_at"),
        Index("ix_traces_status_created", "status", "created_at"),
        Index("ix_traces_project_created", "project_id", "created_at"),
    )


class TraceStepRecord(Base):
    """Individual step within an AI trace."""

    __tablename__ = "trace_steps"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    trace_id = Column(String(64), ForeignKey("traces.id"), nullable=False, index=True)
    step_index = Column(Integer, nullable=False)
    step_type = Column(String(32), nullable=False, index=True)
    latency_ms = Column(Float, default=0.0)
    step_data_json = Column(Text, nullable=False)  # JSON representation of step data
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    trace = relationship("TraceRecord", back_populates="steps")

    __table_args__ = (Index("ix_trace_steps_trace_step_index", "trace_id", "step_index"),)


class WatchdogFindingRecord(Base):
    """Anomalies or business rule violations flagged by Watchdog."""

    __tablename__ = "watchdog_findings"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    project_id = Column(String(64), nullable=False, default="default", index=True)
    rule_name = Column(String(128), nullable=False, index=True)
    severity = Column(String(32), default="medium", index=True)  # info, low, medium, high, critical
    description = Column(Text, nullable=False)
    entity_type = Column(String(64), nullable=False)  # order, refund, product, customer
    entity_id = Column(String(64), nullable=False, index=True)
    trace_id = Column(String(64), nullable=True, index=True)
    details_json = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False, index=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    __table_args__ = (
        Index("ix_watchdog_resolved_detected", "resolved", "detected_at"),
        Index("ix_watchdog_severity_detected", "severity", "detected_at"),
        Index("ix_watchdog_project_resolved", "project_id", "resolved"),
    )


class ApprovalQueueRecord(Base):
    """Human-in-the-loop pending approval requests queued by Guard."""

    __tablename__ = "approval_queue"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    project_id = Column(String(64), nullable=False, default="default", index=True)
    action_type = Column(String(64), nullable=False, index=True)
    tool_name = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False, index=True)
    customer_id = Column(String(64), nullable=True, index=True)
    amount = Column(Float, nullable=True)
    payload_json = Column(Text, nullable=False)
    status = Column(
        String(32), default="pending", index=True
    )  # pending, approved, rejected, edited
    guard_reasons = Column(Text, nullable=True)
    risk_level = Column(String(32), default="high")
    reviewer_id = Column(String(64), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    edited_payload_json = Column(Text, nullable=True)
    idempotency_key = Column(String(128), unique=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)
    decided_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_approval_status_created", "status", "created_at"),
        Index("ix_approval_project_status", "project_id", "status"),
    )
