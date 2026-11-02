"""OpenTelemetry (OTel) Exporter for Argvtix Traces.

Converts native Argvtix Traces and TraceSteps into standard W3C TraceContext
and OpenTelemetry (OTLP) compliant JSON payload structures for export to
Langfuse, Arize Phoenix, Datadog, Jaeger, and OpenTelemetry Collectors.

Adheres to:
- W3C Trace Context Specification (Traceparent format)
- OpenTelemetry GenAI Semantic Conventions (gen_ai.*)
- OTLP JSON / ResourceSpans schema
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from argvtix.trace.schemas import StepType, Trace, TraceStep


def _to_w3c_trace_id(source_id: str) -> str:
    """Converts any string/UUID trace ID into a valid 32-character lowercase hex W3C Trace ID."""
    clean = source_id.replace("-", "").lower()
    if len(clean) == 32 and all(c in "0123456789abcdef" for c in clean):
        return clean
    # Deterministic SHA-256 slice (32 hex characters)
    return hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:32]


def _to_w3c_span_id(source_id: str, step_index: int = 0) -> str:
    """Converts step identity into a valid 16-character lowercase hex W3C Span ID."""
    raw = f"{source_id}:{step_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _to_unix_nano(dt: Optional[datetime]) -> int:
    """Converts a datetime into Unix epoch nanoseconds for OTel timestamps."""
    if dt is None:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1e9)


class OpenTelemetryExporter:
    """Transforms and exports Argvtix Traces into standard OpenTelemetry OTLP structures."""

    def __init__(self, service_name: str = "argvtix-agent-guard", service_version: str = "1.0.0"):
        self.service_name = service_name
        self.service_version = service_version

    def build_traceparent_header(self, trace: Trace, step: Optional[TraceStep] = None) -> str:
        """Builds standard W3C traceparent header: 00-{trace_id}-{span_id}-01."""
        trace_id = _to_w3c_trace_id(trace.trace_id)
        span_id = _to_w3c_span_id(trace.trace_id, step.step_index if step else 0)
        return f"00-{trace_id}-{span_id}-01"

    def step_to_otel_span(self, trace: Trace, step: TraceStep, root_span_id: str) -> dict[str, Any]:
        """Converts an individual Argvtix TraceStep into an OTel Span representation."""
        trace_id = _to_w3c_trace_id(trace.trace_id)
        span_id = _to_w3c_span_id(trace.trace_id, step.step_index)
        parent_span_id = root_span_id if step.step_index > 0 else None

        # Determine Span Kind (1=INTERNAL, 2=SERVER, 3=CLIENT, 4=PRODUCER, 5=CONSUMER)
        span_kind = 1  # INTERNAL default
        if step.step_type == StepType.TOOL_CALL:
            span_kind = 3  # CLIENT (calls external business tool/db)
        elif step.step_type == StepType.LLM_CALL:
            span_kind = 3  # CLIENT (calls external model API)

        # Standard attributes
        workflow_str = getattr(trace, "workflow", "") or "general"
        attributes: list[dict[str, Any]] = [
            {"key": "argvtix.step_type", "value": {"stringValue": step.step_type.value}},
            {"key": "argvtix.step_index", "value": {"intValue": step.step_index}},
            {"key": "argvtix.session_id", "value": {"stringValue": getattr(trace, "session_id", "") or ""}},
            {"key": "argvtix.workflow", "value": {"stringValue": workflow_str}},
        ]

        if trace.customer_id:
            attributes.append({"key": "customer.id", "value": {"stringValue": trace.customer_id}})

        # GenAI Semantic Conventions
        if step.step_type == StepType.LLM_CALL and step.llm_call:
            in_tok = getattr(step.llm_call, "input_tokens", getattr(step.llm_call, "prompt_tokens", 0)) or 0
            out_tok = getattr(step.llm_call, "output_tokens", getattr(step.llm_call, "completion_tokens", 0)) or 0
            cost_val = getattr(step.llm_call, "cost_usd", getattr(step.llm_call, "estimated_cost_usd", None))

            attributes.extend([
                {"key": "gen_ai.system", "value": {"stringValue": "gemini"}},
                {"key": "gen_ai.request.model", "value": {"stringValue": step.llm_call.model or "unknown"}},
                {"key": "gen_ai.usage.prompt_tokens", "value": {"intValue": in_tok}},
                {"key": "gen_ai.usage.completion_tokens", "value": {"intValue": out_tok}},
                {"key": "gen_ai.usage.total_tokens", "value": {"intValue": in_tok + out_tok}},
            ])
            if cost_val is not None:
                attributes.append({
                    "key": "gen_ai.usage.cost_usd",
                    "value": {"doubleValue": float(cost_val)}
                })

        # Action Guard details
        if step.step_type == StepType.GUARD_DECISION and step.guard_decision:
            rule_str = getattr(step.guard_decision, "policy_rule_triggered", getattr(step.guard_decision, "policy_version", "default"))
            risk_str = getattr(step.guard_decision, "risk_level", "normal")
            action_str = getattr(step.guard_decision, "action", "")
            attributes.extend([
                {"key": "argvtix.guard.action", "value": {"stringValue": action_str}},
                {"key": "argvtix.guard.decision", "value": {"stringValue": step.guard_decision.decision.value}},
                {"key": "argvtix.guard.rule", "value": {"stringValue": rule_str}},
                {"key": "argvtix.guard.risk_level", "value": {"stringValue": risk_str}},
            ])

        # Tool Call details
        if step.step_type == StepType.TOOL_CALL and step.tool_call:
            is_succ = getattr(step.tool_call, "is_success", True)
            tool_status = "executed" if is_succ else "failed"
            attributes.extend([
                {"key": "argvtix.tool.name", "value": {"stringValue": step.tool_call.tool_name}},
                {"key": "argvtix.tool.status", "value": {"stringValue": tool_status}},
            ])

        # Status code (1=OK, 2=ERROR, 0=UNSET)
        is_error = step.step_type == StepType.ERROR or (
            step.tool_call and not getattr(step.tool_call, "is_success", True)
        )
        status_code = 2 if is_error else 1
        status_message = step.error.error_message if (step.error and step.error.error_message) else "OK"

        start_time_unix = _to_unix_nano(step.timestamp)
        # Duration in nanoseconds
        duration_ns = int((step.duration_ms or 1.0) * 1e6)
        end_time_unix = start_time_unix + duration_ns

        span_obj: dict[str, Any] = {
            "traceId": trace_id,
            "spanId": span_id,
            "name": f"{step.step_type.value}:{step.step_index}",
            "kind": span_kind,
            "startTimeUnixNano": str(start_time_unix),
            "endTimeUnixNano": str(end_time_unix),
            "attributes": attributes,
            "status": {
                "code": status_code,
                "message": status_message,
            },
        }

        if parent_span_id:
            span_obj["parentSpanId"] = parent_span_id

        return span_obj

    def trace_to_otlp_json(self, trace: Trace) -> dict[str, Any]:
        """Converts an entire Argvtix Trace into an OTLP-compliant ResourceSpans payload."""
        trace_id = _to_w3c_trace_id(trace.trace_id)
        root_span_id = _to_w3c_span_id(trace.trace_id, 0)

        # Root Agent Execution Span
        root_start_unix = _to_unix_nano(trace.created_at)
        latency = getattr(trace, "total_latency_ms", getattr(trace, "total_duration_ms", 10.0)) or 10.0
        total_duration_ns = int(latency * 1e6)
        root_end_unix = root_start_unix + total_duration_ns

        workflow_name = getattr(trace, "workflow", "") or (trace.tags[0] if (getattr(trace, "tags", None) and isinstance(trace.tags, list)) else "general")
        input_str = getattr(trace, "input_text", getattr(trace, "user_input", ""))

        root_attributes: list[dict[str, Any]] = [
            {"key": "argvtix.trace_id", "value": {"stringValue": trace.trace_id}},
            {"key": "argvtix.session_id", "value": {"stringValue": getattr(trace, "session_id", "") or ""}},
            {"key": "argvtix.workflow", "value": {"stringValue": workflow_name}},
            {"key": "argvtix.user_input", "value": {"stringValue": input_str or ""}},
            {"key": "argvtix.status", "value": {"stringValue": trace.status.value}},
            {"key": "argvtix.total_tokens", "value": {"intValue": getattr(trace, "total_tokens", 0) or 0}},
            {"key": "argvtix.total_cost_usd", "value": {"doubleValue": float(getattr(trace, "total_cost_usd", 0.0) or 0.0)}},
        ]

        if hasattr(trace, "tags") and trace.tags:
            if isinstance(trace.tags, list):
                for idx, tag in enumerate(trace.tags):
                    root_attributes.append({"key": f"argvtix.tag.{idx}", "value": {"stringValue": str(tag)}})
            elif isinstance(trace.tags, dict):
                for k, v in trace.tags.items():
                    root_attributes.append({"key": f"argvtix.tag.{k}", "value": {"stringValue": str(v)}})

        root_span: dict[str, Any] = {
            "traceId": trace_id,
            "spanId": root_span_id,
            "name": f"AgentInteraction:{workflow_name}",
            "kind": 2,  # SERVER
            "startTimeUnixNano": str(root_start_unix),
            "endTimeUnixNano": str(root_end_unix),
            "attributes": root_attributes,
            "status": {
                "code": 1 if trace.status.value != "failed" else 2,
                "message": "COMPLETED" if trace.status.value != "failed" else "FAILED",
            },
        }

        spans = [root_span]
        for step in trace.steps:
            spans.append(self.step_to_otel_span(trace, step, root_span_id))

        resource_spans = {
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": self.service_name}},
                    {"key": "service.version", "value": {"stringValue": self.service_version}},
                    {"key": "telemetry.sdk.language", "value": {"stringValue": "python"}},
                    {"key": "telemetry.sdk.name", "value": {"stringValue": "argvtix-otel-exporter"}},
                ]
            },
            "scopeSpans": [
                {
                    "scope": {
                        "name": "argvtix.trace.otel_export",
                        "version": "1.0.0",
                    },
                    "spans": spans,
                }
            ],
        }

        return {"resourceSpans": [resource_spans]}

    def export_to_file(self, trace: Trace, output_path: str | Path) -> Path:
        """Exports the OTLP JSON representation to a file."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = self.trace_to_otlp_json(trace)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return target
