"""
Trace Store — Database persistence & retrieval for AI traces.

Provides high-level functions to save a Pydantic v2 Trace object into the SQL
database (SQLite / PostgreSQL) and reconstruct it back into a validated Trace object.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from argvtix.db.models import TraceRecord, TraceStepRecord
from argvtix.trace.schemas import StepType, Trace, TraceStatus, TraceStep


def save_trace(db: Session, trace: Trace) -> TraceRecord:
    """
    Persist a Pydantic Trace and its TraceSteps into the database.
    If a trace with this ID already exists, raises ValueError.
    """
    existing = db.query(TraceRecord).filter_by(id=trace.trace_id).first()
    if existing:
        raise ValueError(f"Trace with ID {trace.trace_id} already exists in database.")

    # Extract output text if available
    output_text = None
    output_steps = trace.get_steps_by_type(StepType.OUTPUT)
    if output_steps and output_steps[-1].output:
        output_text = getattr(
            output_steps[-1].output,
            "response_text",
            getattr(output_steps[-1].output, "output_text", None),
        )

    # Extract error message if available
    error_msg = None
    error_steps = trace.get_steps_by_type(StepType.ERROR)
    if error_steps and error_steps[-1].error:
        error_msg = error_steps[-1].error.error_message

    workflow_type = trace.metadata.get("workflow_type") or trace.metadata.get("workflow_id")
    if not workflow_type and trace.tags:
        workflow_type = trace.tags[0]

    record = TraceRecord(
        id=trace.trace_id,
        project_id=getattr(trace, "project_id", "default") or "default",
        session_id=trace.session_id,
        user_id=trace.customer_id,
        channel=trace.metadata.get("channel", "web"),
        workflow_type=workflow_type,
        status=trace.status.value,
        input_text=trace.input_text,
        output_text=output_text,
        error_message=error_msg,
        total_latency_ms=trace.total_latency_ms,
        total_cost_usd=trace.total_cost_usd,
        total_tokens=trace.total_tokens,
        tags_json=json.dumps(trace.tags),
        metadata_json=json.dumps(trace.metadata),
        created_at=trace.created_at or datetime.now(UTC),
        completed_at=trace.completed_at or datetime.now(UTC),
    )
    db.add(record)

    # Add child steps
    for step in trace.steps:
        step_rec = TraceStepRecord(
            id=step.step_id,
            trace_id=trace.trace_id,
            step_index=step.step_index,
            step_type=step.step_type.value,
            latency_ms=step.duration_ms or 0.0,
            step_data_json=step.model_dump_json(),
            created_at=step.timestamp or datetime.now(UTC),
        )
        db.add(step_rec)

    db.commit()
    db.refresh(record)
    return record


def get_trace(db: Session, trace_id: str, project_id: str | None = None) -> Trace | None:
    """
    Fetch a TraceRecord from database by trace_id and deserialize it
    back into a Pydantic v2 Trace object. Returns None if not found.
    """
    query = db.query(TraceRecord).filter(TraceRecord.id == trace_id)
    if project_id:
        query = query.filter(TraceRecord.project_id == project_id)
    record = query.first()
    if not record:
        return None

    # Reconstruct steps
    step_records = (
        db.query(TraceStepRecord)
        .filter(TraceStepRecord.trace_id == trace_id)
        .order_by(TraceStepRecord.step_index.asc())
        .all()
    )

    steps: list[TraceStep] = []
    for s_rec in step_records:
        step_dict = json.loads(s_rec.step_data_json)
        step_obj = TraceStep.model_validate(step_dict)
        steps.append(step_obj)

    tags = json.loads(record.tags_json) if record.tags_json else []
    metadata = json.loads(record.metadata_json) if record.metadata_json else {}

    return Trace(
        trace_id=record.id,
        project_id=record.project_id,
        session_id=record.session_id,
        customer_id=record.user_id,
        input_text=record.input_text,
        input_language=metadata.get("input_language", "hinglish"),
        prompt_version=metadata.get("prompt_version", "v1"),
        model_version=metadata.get("model_version", "gemini-2.0-flash"),
        steps=steps,
        status=TraceStatus(record.status),
        created_at=record.created_at,
        completed_at=record.completed_at,
        total_tokens=record.total_tokens or 0,
        total_cost_usd=record.total_cost_usd or 0.0,
        total_latency_ms=record.total_latency_ms or 0.0,
        step_count=len(steps),
        tags=tags,
        metadata=metadata,
    )


def list_trace_records(
    db: Session,
    workflow_type: str | None = None,
    status_filter: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TraceRecord]:
    """List trace records with optional filters and pagination."""
    query = db.query(TraceRecord)
    if project_id:
        query = query.filter(TraceRecord.project_id == project_id)
    if workflow_type:
        query = query.filter(TraceRecord.workflow_type == workflow_type)
    if status_filter:
        query = query.filter(TraceRecord.status == status_filter)

    return query.order_by(TraceRecord.created_at.desc()).offset(offset).limit(limit).all()
