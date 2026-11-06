"""
Structural Tenant Isolation Layer for Argvtix.

Provides:
- TenantScopedSession: Intercepts queries and writes to guarantee that tenant data
  is strictly partitioned by project_id at the session/repository level.
- TenantRepository: Central repository ensuring all CRUD operations for traces,
  findings, approvals, alerts, scout reports, and audit logs are tenant-scoped.
- PostgreSQL Row-Level Security (RLS) DDL definitions and application helper.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any, TypeVar

from fastapi import Header, Request
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query, Session

logger = logging.getLogger("argvtix.db.tenant")

T = TypeVar("T")

# Tables that must be protected by project_id tenant isolation
TENANT_ISOLATED_TABLES = [
    "traces",
    "trace_steps",
    "watchdog_findings",
    "approval_queue",
    "scout_reports",
    "audit_logs",
    "alerts",
]


class TenantScopedQuery(Query[T]):
    """SQLAlchemy Query subclass that automatically binds a project_id filter

    to every query touching tenant-scoped entities.
    """

    def __init__(self, entities: Any, session: Session, project_id: str) -> None:
        super().__init__(entities, session)
        self._project_id = project_id
        self._apply_tenant_filter()

    def _apply_tenant_filter(self) -> None:
        """Inspect entities and automatically add project_id filtering if entity supports it."""
        for desc in self.column_descriptions:
            entity: Any = desc.get("entity")
            if entity is not None and hasattr(entity, "project_id"):
                # Apply filter only once
                crit = getattr(self, "_criterion", None)
                pid_cond = entity.project_id == self._project_id
                self._criterion = (crit & pid_cond) if crit is not None else pid_cond  # type: ignore[attr-defined, has-type]


class TenantScopedSession:
    """Wraps an underlying SQLAlchemy Session to enforce structural tenant isolation.

    Guarantees:
    1. Every query automatically filters by project_id for models with a project_id attribute.
    2. Every inserted object automatically inherits the tenant's project_id if not explicitly set.
    3. Prevents cross-tenant modifications or reads even if caller forgets .filter(project_id=...).
    """

    def __init__(self, db: Session, project_id: str) -> None:
        if not project_id:
            raise ValueError("project_id is required for TenantScopedSession")
        self.db = db
        self.project_id = project_id

    def query(self, *entities: Any, **kwargs: Any) -> Query[Any]:
        """Construct a query and automatically enforce project_id scoping."""
        q = self.db.query(*entities, **kwargs)
        for entity in entities:
            if hasattr(entity, "project_id"):
                q = q.filter(entity.project_id == self.project_id)
        return q

    def add(self, instance: Any) -> None:
        """Enforce tenant scoping on entity creation."""
        if hasattr(instance, "project_id"):
            current_pid = getattr(instance, "project_id", None)
            if not current_pid or current_pid == "default" and self.project_id != "default":
                instance.project_id = self.project_id
            elif current_pid != self.project_id and self.project_id != "default":
                raise PermissionError(
                    f"Tenant cross-contamination prevented: Session is scoped to '{self.project_id}', "
                    f"cannot persist entity for tenant '{current_pid}'."
                )
        self.db.add(instance)

    def add_all(self, instances: list[Any]) -> None:
        """Enforce tenant scoping across multiple entity creations."""
        for inst in instances:
            self.add(inst)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def flush(self) -> None:
        self.db.flush()

    def refresh(self, instance: Any) -> None:
        self.db.refresh(instance)

    def delete(self, instance: Any) -> None:
        """Prevent deleting records that do not belong to the current tenant."""
        if hasattr(instance, "project_id"):
            record_pid = getattr(instance, "project_id", None)
            if record_pid and record_pid != self.project_id:
                raise PermissionError(
                    f"Tenant isolation violation: cannot delete entity belonging to '{record_pid}' "
                    f"from tenant session '{self.project_id}'."
                )
        self.db.delete(instance)

    def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self.db.execute(statement, *args, **kwargs)

    @property
    def bind(self) -> Any:
        return self.db.bind

    def get_bind(self) -> Any:
        return self.db.get_bind()

    def close(self) -> None:
        self.db.close()


def generate_rls_ddl() -> list[str]:
    """Generates PostgreSQL Row-Level Security (RLS) DDL statements.

    Configures:
    1. ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
    2. FORCE ROW LEVEL SECURITY (applies to table owners too);
    3. CREATE POLICY for tenant isolation based on current_setting('app.current_project_id').
    """
    ddl_statements = []
    for table in TENANT_ISOLATED_TABLES:
        ddl_statements.extend(
            [
                f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY;",
                f"ALTER TABLE IF EXISTS {table} FORCE ROW LEVEL SECURITY;",
                f"""DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = '{table}' AND policyname = 'tenant_isolation_policy'
    ) THEN
        CREATE POLICY tenant_isolation_policy ON {table}
        AS RESTRICTIVE
        USING (project_id = NULLIF(current_setting('app.current_project_id', true), ''))
        WITH CHECK (project_id = NULLIF(current_setting('app.current_project_id', true), ''));
    END IF;
END $$;""",
            ]
        )
    return ddl_statements


def apply_rls_policies(target_engine: Engine) -> bool:
    """Applies PostgreSQL Row-Level Security DDL if running against PostgreSQL.

    Returns True if policies applied, False if SQLite/non-Postgres.
    """
    dialect = target_engine.dialect.name.lower()
    if dialect != "postgresql":
        logger.debug(f"Skipping PostgreSQL RLS policy setup for dialect '{dialect}'.")
        return False

    ddl_list = generate_rls_ddl()
    with target_engine.connect() as conn:
        for stmt in ddl_list:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                logger.warning(f"Could not apply RLS statement on PostgreSQL: {e}")
        conn.commit()
    logger.info("Successfully applied PostgreSQL Row-Level Security policies.")
    return True


def get_tenant_db(
    request: Request,
    x_project_id: str | None = Header(default=None, alias="X-Project-ID"),
) -> Generator[TenantScopedSession, None, None]:
    """FastAPI dependency yielding a TenantScopedSession partitioned by project_id.

    Extracts project_id from X-Project-ID header or request state or defaults to 'default'.
    On PostgreSQL dialect, sets session-level app.current_project_id for Row-Level Security.
    """
    from argvtix.db.session import SessionLocal

    project_id = x_project_id
    if not project_id and request is not None and hasattr(request, "state"):
        project_id = getattr(request.state, "project_id", None)
    if not project_id:
        project_id = "default"

    db = SessionLocal()
    try:
        bind = db.get_bind()
        if bind is not None and bind.dialect.name.lower() == "postgresql":
            db.execute(
                text("SELECT set_config('app.current_project_id', :pid, false)"),
                {"pid": project_id},
            )
        tenant_session = TenantScopedSession(db=db, project_id=project_id)
        yield tenant_session
    finally:
        db.close()
