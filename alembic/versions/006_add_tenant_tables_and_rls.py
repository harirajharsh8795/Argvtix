"""add tenant tables trace_steps project_id and postgres rls

Revision ID: 006_add_tenant_tables_and_rls
Revises: 005_add_refund_idempotency_key
Create Date: 2026-11-06 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '006_add_tenant_tables_and_rls'
down_revision: str | None = '005_add_refund_idempotency_key'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = [
    "traces",
    "trace_steps",
    "watchdog_findings",
    "approval_queue",
    "scout_reports",
    "audit_logs",
    "alerts",
]


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name.lower()

    # 1. Add project_id to trace_steps
    with op.batch_alter_table('trace_steps', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('project_id', sa.String(length=64), nullable=False, server_default='default')
        )
        batch_op.create_index('ix_trace_steps_project_id', ['project_id'])

    # 2. Create scout_reports table
    op.create_table(
        'scout_reports',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('project_id', sa.String(length=64), nullable=False, server_default='default'),
        sa.Column('scope_id', sa.String(length=64), nullable=False),
        sa.Column('target_name', sa.String(length=128), nullable=False),
        sa.Column('grade', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('pass_rate', sa.Float(), nullable=False),
        sa.Column('report_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scout_reports_project_id', 'scout_reports', ['project_id'])

    # 3. Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('project_id', sa.String(length=64), nullable=False, server_default='default'),
        sa.Column('actor', sa.String(length=128), nullable=False),
        sa.Column('action', sa.String(length=128), nullable=False),
        sa.Column('target_type', sa.String(length=64), nullable=False),
        sa.Column('target_id', sa.String(length=128), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_logs_project_id', 'audit_logs', ['project_id'])

    # 4. Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('project_id', sa.String(length=64), nullable=False, server_default='default'),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('resolved', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_alerts_project_id', 'alerts', ['project_id'])

    # 5. Apply PostgreSQL Row-Level Security if PostgreSQL
    if dialect == "postgresql":
        for tbl in TENANT_TABLES:
            op.execute(f"ALTER TABLE IF EXISTS {tbl} ENABLE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE IF EXISTS {tbl} FORCE ROW LEVEL SECURITY;")
            op.execute(
                f"""DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = '{tbl}' AND policyname = 'tenant_isolation_policy'
    ) THEN
        CREATE POLICY tenant_isolation_policy ON {tbl}
        AS RESTRICTIVE
        USING (project_id = NULLIF(current_setting('app.current_project_id', true), ''))
        WITH CHECK (project_id = NULLIF(current_setting('app.current_project_id', true), ''));
    END IF;
END $$;"""
            )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name.lower()

    if dialect == "postgresql":
        for tbl in reversed(TENANT_TABLES):
            op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {tbl};")
            op.execute(f"ALTER TABLE IF EXISTS {tbl} NO FORCE ROW LEVEL SECURITY;")
            op.execute(f"ALTER TABLE IF EXISTS {tbl} DISABLE ROW LEVEL SECURITY;")

    op.drop_index('ix_alerts_project_id', table_name='alerts')
    op.drop_table('alerts')

    op.drop_index('ix_audit_logs_project_id', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_index('ix_scout_reports_project_id', table_name='scout_reports')
    op.drop_table('scout_reports')

    with op.batch_alter_table('trace_steps', schema=None) as batch_op:
        batch_op.drop_index('ix_trace_steps_project_id')
        batch_op.drop_column('project_id')
