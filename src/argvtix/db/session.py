"""
Database Engine & Session Management
Supports both PostgreSQL (production / Docker) and SQLite (local dev & testing).
Configures production connection pooling, pre-ping liveness, and pool recycling.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Load database URL from environment or default to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./argvtix.db")

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}

# Connection pooling parameters
pool_kwargs: dict[str, object] = {
    "pool_pre_ping": True,
}

if not is_sqlite:
    # Production PostgreSQL connection pooling
    pool_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "20"))
    pool_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    pool_kwargs["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    pool_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "1800"))
elif not DATABASE_URL.endswith(":memory:"):
    # File-based SQLite pooling
    pool_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "20"))
    pool_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "30"))
    pool_kwargs["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    pool_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "1800"))

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    connect_args=connect_args,
    **pool_kwargs,
)

if is_sqlite and not DATABASE_URL.endswith(":memory:"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """Create all registered database tables and ensure column/index schema synchronization."""
    eng = target_engine or engine
    # Import models to ensure they are registered with Base.metadata
    from argvtix.db import models  # noqa: F401

    Base.metadata.create_all(bind=eng)

    # Automatic schema migration for existing SQLite dev databases
    try:
        from sqlalchemy import inspect, text

        inspector = inspect(eng)
        for tbl in ["traces", "watchdog_findings", "approval_queue"]:
            if tbl in inspector.get_table_names():
                columns = [c["name"] for c in inspector.get_columns(tbl)]
                if "project_id" not in columns:
                    with eng.connect() as conn:
                        conn.execute(
                            text(f"ALTER TABLE {tbl} ADD COLUMN project_id VARCHAR(64) DEFAULT 'default'")
                        )
                        conn.commit()

        if "refunds" in inspector.get_table_names():
            refund_cols = [c["name"] for c in inspector.get_columns("refunds")]
            if "idempotency_key" not in refund_cols:
                with eng.connect() as conn:
                    conn.execute(
                        text("ALTER TABLE refunds ADD COLUMN idempotency_key VARCHAR(128)")
                    )
                    conn.commit()
            # Ensure unique index exists on idempotency_key
            indexes = [idx["name"] for idx in inspector.get_indexes("refunds")]
            if "ix_refunds_idempotency_key" not in indexes:
                with eng.connect() as conn:
                    conn.execute(
                        text("CREATE UNIQUE INDEX IF NOT EXISTS ix_refunds_idempotency_key ON refunds (idempotency_key)")
                    )
                    conn.commit()
    except Exception:
        pass

