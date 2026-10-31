"""add project_id column to traces, watchdog_findings, and approval_queue

Revision ID: 003_add_project_id
Revises: 002_add_approval_queue
Create Date: 2026-10-25 04:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_project_id'
down_revision: Union[str, None] = '002_add_approval_queue'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add project_id to traces
    op.add_column('traces', sa.Column('project_id', sa.String(length=64), nullable=False, server_default='default'))
    op.create_index(op.f('ix_traces_project_id'), 'traces', ['project_id'], unique=False)

    # 2. Add project_id and suggested_action to watchdog_findings
    op.add_column('watchdog_findings', sa.Column('project_id', sa.String(length=64), nullable=False, server_default='default'))
    op.add_column('watchdog_findings', sa.Column('suggested_action', sa.Text(), nullable=True))
    op.create_index(op.f('ix_watchdog_findings_project_id'), 'watchdog_findings', ['project_id'], unique=False)

    # 3. Add project_id to approval_queue
    op.add_column('approval_queue', sa.Column('project_id', sa.String(length=64), nullable=False, server_default='default'))
    op.create_index(op.f('ix_approval_queue_project_id'), 'approval_queue', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_approval_queue_project_id'), table_name='approval_queue')
    op.drop_column('approval_queue', 'project_id')

    op.drop_index(op.f('ix_watchdog_findings_project_id'), table_name='watchdog_findings')
    op.drop_column('watchdog_findings', 'suggested_action')
    op.drop_column('watchdog_findings', 'project_id')

    op.drop_index(op.f('ix_traces_project_id'), table_name='traces')
    op.drop_column('traces', 'project_id')
