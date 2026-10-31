"""add refund idempotency key and unique constraint

Revision ID: 005_add_refund_idempotency_key
Revises: 004_performance_indexes
Create Date: 2026-10-29 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_refund_idempotency_key'
down_revision: Union[str, None] = '004_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add idempotency_key column to refunds
    op.add_column('refunds', sa.Column('idempotency_key', sa.String(length=128), nullable=True))
    op.create_index('ix_refunds_idempotency_key', 'refunds', ['idempotency_key'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_refunds_idempotency_key', table_name='refunds')
    op.drop_column('refunds', 'idempotency_key')
