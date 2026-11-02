"""add performance indexes for latency and query optimization

Revision ID: 004_performance_indexes
Revises: 003_add_project_id
Create Date: 2026-10-27 17:35:00

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '004_performance_indexes'
down_revision: str | None = '003_add_project_id'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Orders
    op.create_index('ix_orders_status', 'orders', ['status'], unique=False)
    op.create_index('ix_orders_customer_created', 'orders', ['customer_id', 'created_at'], unique=False)
    op.create_index('ix_orders_status_created', 'orders', ['status', 'created_at'], unique=False)

    # 2. Payments
    op.create_index('ix_payments_status', 'payments', ['status'], unique=False)
    op.create_index('ix_payments_order_status', 'payments', ['order_id', 'status'], unique=False)
    op.create_index('ix_payments_customer_created', 'payments', ['customer_id', 'created_at'], unique=False)

    # 3. Refunds
    op.create_index('ix_refunds_status', 'refunds', ['status'], unique=False)
    op.create_index('ix_refunds_order_status', 'refunds', ['order_id', 'status'], unique=False)
    op.create_index('ix_refunds_customer_created', 'refunds', ['customer_id', 'created_at'], unique=False)

    # 4. Support Tickets
    op.create_index('ix_support_tickets_status', 'support_tickets', ['status'], unique=False)
    op.create_index('ix_support_tickets_status_priority', 'support_tickets', ['status', 'priority'], unique=False)

    # 5. Ledger Entries
    op.create_index('ix_ledger_customer_type', 'ledger_entries', ['customer_id', 'entry_type'], unique=False)

    # 6. Traces & Steps
    op.create_index('ix_traces_workflow_created', 'traces', ['workflow_type', 'created_at'], unique=False)
    op.create_index('ix_traces_status_created', 'traces', ['status', 'created_at'], unique=False)
    op.create_index('ix_traces_project_created', 'traces', ['project_id', 'created_at'], unique=False)
    op.create_index('ix_trace_steps_trace_step_index', 'trace_steps', ['trace_id', 'step_index'], unique=False)

    # 7. Watchdog Findings & Approvals
    op.create_index('ix_watchdog_resolved_detected', 'watchdog_findings', ['resolved', 'detected_at'], unique=False)
    op.create_index('ix_watchdog_severity_detected', 'watchdog_findings', ['severity', 'detected_at'], unique=False)
    op.create_index('ix_watchdog_project_resolved', 'watchdog_findings', ['project_id', 'resolved'], unique=False)
    op.create_index('ix_approval_status_created', 'approval_queue', ['status', 'created_at'], unique=False)
    op.create_index('ix_approval_project_status', 'approval_queue', ['project_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_approval_project_status', table_name='approval_queue')
    op.drop_index('ix_approval_status_created', table_name='approval_queue')
    op.drop_index('ix_watchdog_project_resolved', table_name='watchdog_findings')
    op.drop_index('ix_watchdog_severity_detected', table_name='watchdog_findings')
    op.drop_index('ix_watchdog_resolved_detected', table_name='watchdog_findings')
    op.drop_index('ix_trace_steps_trace_step_index', table_name='trace_steps')
    op.drop_index('ix_traces_project_created', table_name='traces')
    op.drop_index('ix_traces_status_created', table_name='traces')
    op.drop_index('ix_traces_workflow_created', table_name='traces')
    op.drop_index('ix_ledger_customer_type', table_name='ledger_entries')
    op.drop_index('ix_support_tickets_status_priority', table_name='support_tickets')
    op.drop_index('ix_support_tickets_status', table_name='support_tickets')
    op.drop_index('ix_refunds_customer_created', table_name='refunds')
    op.drop_index('ix_refunds_order_status', table_name='refunds')
    op.drop_index('ix_refunds_status', table_name='refunds')
    op.drop_index('ix_payments_customer_created', table_name='payments')
    op.drop_index('ix_payments_order_status', table_name='payments')
    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_index('ix_orders_status_created', table_name='orders')
    op.drop_index('ix_orders_customer_created', table_name='orders')
    op.drop_index('ix_orders_status', table_name='orders')
