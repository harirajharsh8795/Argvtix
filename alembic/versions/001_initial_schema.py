"""initial schema creation

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-10-24 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Traces table
    op.create_table(
        'traces',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('workflow', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default='SUCCESS'),
        sa.Column('total_latency_ms', sa.Float(), nullable=False, default=0.0),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_input', sa.Text(), nullable=True),
        sa.Column('agent_response', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
    )

    # 2. Trace steps table
    op.create_table(
        'trace_steps',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('trace_id', sa.String(length=64), sa.ForeignKey('traces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_type', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=False, default=0.0),
        sa.Column('inputs_json', sa.Text(), nullable=True),
        sa.Column('outputs_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('customer_id', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default='PENDING'),
        sa.Column('total_amount', sa.Float(), nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    )

    # 4. Order items table
    op.create_table(
        'order_items',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('order_id', sa.String(length=64), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sku', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, default=1),
        sa.Column('unit_price', sa.Float(), nullable=False),
        sa.Column('line_total', sa.Float(), nullable=False),
    )

    # 5. Payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('order_id', sa.String(length=64), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default='SUCCESS'),
        sa.Column('payment_method', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 6. Refunds table
    op.create_table(
        'refunds',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('order_id', sa.String(length=64), nullable=False),
        sa.Column('payment_id', sa.String(length=64), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default='COMPLETED'),
        sa.Column('reason', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 7. Inventory items table
    op.create_table(
        'inventory_items',
        sa.Column('sku', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('quantity_available', sa.Integer(), nullable=False, default=0),
        sa.Column('category', sa.String(length=64), nullable=True),
    )

    # 8. Customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=128), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('tier', sa.String(length=32), nullable=True, default='STANDARD'),
    )

    # 9. Support tickets table
    op.create_table(
        'tickets',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('customer_id', sa.String(length=64), nullable=False),
        sa.Column('order_id', sa.String(length=64), nullable=True),
        sa.Column('subject', sa.String(length=256), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, default='OPEN'),
        sa.Column('priority', sa.String(length=32), nullable=False, default='MEDIUM'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 10. RAG Documents table
    op.create_table(
        'rag_documents',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False),
    )

    # 11. Watchdog Findings table
    op.create_table(
        'watchdog_findings',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('rule_name', sa.String(length=128), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=True),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('watchdog_findings')
    op.drop_table('rag_documents')
    op.drop_table('tickets')
    op.drop_table('customers')
    op.drop_table('inventory_items')
    op.drop_table('refunds')
    op.drop_table('payments')
    op.drop_table('order_items')
    op.drop_table('orders')
    op.drop_table('trace_steps')
    op.drop_table('traces')
