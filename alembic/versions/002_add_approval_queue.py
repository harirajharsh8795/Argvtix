"""add approval queue table

Revision ID: 002_add_approval_queue
Revises: 001_initial_schema
Create Date: 2026-10-25 01:40:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_add_approval_queue'
down_revision: str | None = '001_initial_schema'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'approval_queue',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('tool_name', sa.String(length=64), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('customer_id', sa.String(length=64), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True, default='pending'),
        sa.Column('guard_reasons', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(length=32), nullable=True, default='high'),
        sa.Column('reviewer_id', sa.String(length=64), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('edited_payload_json', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_queue_action_type'), 'approval_queue', ['action_type'], unique=False)
    op.create_index(op.f('ix_approval_queue_customer_id'), 'approval_queue', ['customer_id'], unique=False)
    op.create_index(op.f('ix_approval_queue_entity_id'), 'approval_queue', ['entity_id'], unique=False)
    op.create_index(op.f('ix_approval_queue_idempotency_key'), 'approval_queue', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_approval_queue_status'), 'approval_queue', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_approval_queue_status'), table_name='approval_queue')
    op.drop_index(op.f('ix_approval_queue_idempotency_key'), table_name='approval_queue')
    op.drop_index(op.f('ix_approval_queue_entity_id'), table_name='approval_queue')
    op.drop_index(op.f('ix_approval_queue_customer_id'), table_name='approval_queue')
    op.drop_index(op.f('ix_approval_queue_action_type'), table_name='approval_queue')
    op.drop_table('approval_queue')
