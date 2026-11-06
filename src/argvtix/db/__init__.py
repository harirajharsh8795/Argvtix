"""
ARGVTIX Database Layer
Provides SQLAlchemy ORM models, session factories, and database initialization.
"""

from argvtix.db.models import (
    Base,
    Customer,
    InventoryLog,
    Order,
    OrderItem,
    Payment,
    Product,
    Refund,
    SupportTicket,
    TraceRecord,
    TraceStepRecord,
    WatchdogFindingRecord,
)
from argvtix.db.session import SessionLocal, engine, get_db, init_db
from argvtix.db.tenant import TenantScopedSession, get_tenant_db

__all__ = [
    "get_db",
    "get_tenant_db",
    "TenantScopedSession",
    "init_db",
    "engine",
    "SessionLocal",
    "Base",
    "Customer",
    "Product",
    "Order",
    "OrderItem",
    "Payment",
    "Refund",
    "InventoryLog",
    "SupportTicket",
    "TraceRecord",
    "TraceStepRecord",
    "WatchdogFindingRecord",
]
