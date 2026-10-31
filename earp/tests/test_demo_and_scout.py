"""Test Suite for End-to-End Demo, Scout Black-Box Audit, OTel Export, and Spend Guard."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from earp.scout.probes.registry import ProbeRegistry
from earp.scout.report import AuditGrade, AuditStatus, calculate_grade
from earp.scout.runner import ScoutRunner
from earp.scout.safety import ScoutSafetyController
from earp.scout.scope import ScopeConfig, load_scope_from_yaml
from earp.target_app.spend_guard import LLMSpendGuard
from earp.trace.otel_export import OpenTelemetryExporter, _to_w3c_span_id, _to_w3c_trace_id
from earp.trace.schemas import (
    GuardDecision,
    GuardDecisionData,
    LLMCallData,
    OutputData,
    StepType,
    ToolCallData,
    Trace,
    TraceStep,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestOpenTelemetryExporter:
    """Verifies Proofline to OpenTelemetry (OTel / W3C) export pipeline."""

    def test_w3c_trace_and_span_id_normalization(self):
        raw_uuid = "e3952d0c-64d1-4c43-8dc9-4d76580be602"
        w3c_trace_id = _to_w3c_trace_id(raw_uuid)
        assert len(w3c_trace_id) == 32
        assert all(c in "0123456789abcdef" for c in w3c_trace_id)

        w3c_span_id = _to_w3c_span_id(raw_uuid, 2)
        assert len(w3c_span_id) == 16
        assert all(c in "0123456789abcdef" for c in w3c_span_id)

    def test_traceparent_header_generation(self):
        trace = Trace(
            input_text="Refund check",
            prompt_version="v2",
            model_version="gemini-2.5-pro",
        )
        exporter = OpenTelemetryExporter()
        header = exporter.build_traceparent_header(trace)
        parts = header.split("-")
        assert len(parts) == 4
        assert parts[0] == "00"
        assert len(parts[1]) == 32
        assert len(parts[2]) == 16
        assert parts[3] == "01"

    def test_full_trace_export_to_otlp_json(self, tmp_path):
        trace = Trace(
            input_text="Cancel order 1042",
            prompt_version="v1",
            model_version="gemini-2.5-pro",
            customer_id="cust_101",
            tags=["cancellation", "priority"],
        )

        # Step 1: LLM Call
        trace.add_step(
            TraceStep(
                step_index=1,
                step_type=StepType.LLM_CALL,
                llm_call=LLMCallData(
                    model="gemini-2.5-pro",
                    prompt_version="v1",
                    input_text="Cancel order 1042",
                    input_tokens=45,
                    output_tokens=15,
                    cost_usd=0.00012,
                ),
                duration_ms=120.0,
            )
        )

        # Step 2: Guard Decision
        trace.add_step(
            TraceStep(
                step_index=2,
                step_type=StepType.GUARD_DECISION,
                guard_decision=GuardDecisionData(
                    action="cancel_order",
                    entity_id="ord_1042",
                    decision=GuardDecision.ALLOW,
                    policy_version="1.0.0",
                    reasons=["Cancellation window valid"],
                ),
                duration_ms=5.0,
            )
        )

        # Step 3: Tool Call
        trace.add_step(
            TraceStep(
                step_index=3,
                step_type=StepType.TOOL_CALL,
                tool_call=ToolCallData(
                    tool_name="cancel_order",
                    tool_args={"order_id": "1042"},
                    tool_result={"status": "cancelled"},
                    is_success=True,
                    is_write=True,
                ),
                duration_ms=45.0,
            )
        )

        # Step 4: Output
        trace.add_step(
            TraceStep(
                step_index=4,
                step_type=StepType.OUTPUT,
                output=OutputData(
                    response_text="Order 1042 has been cancelled.",
                    language="en",
                ),
                duration_ms=10.0,
            )
        )

        exporter = OpenTelemetryExporter(service_name="proofline-test")
        otlp = exporter.trace_to_otlp_json(trace)

        assert "resourceSpans" in otlp
        resource_spans = otlp["resourceSpans"][0]
        spans = resource_spans["scopeSpans"][0]["spans"]

        # 1 Root span + 4 Step spans = 5 total spans
        assert len(spans) == 5

        # Check GenAI attributes on LLM span (0-indexed step)
        llm_span = next(s for s in spans if s["name"] == "llm_call:0")
        attr_dict = {a["key"]: a["value"] for a in llm_span["attributes"]}
        assert attr_dict["gen_ai.system"]["stringValue"] == "gemini"
        assert attr_dict["gen_ai.request.model"]["stringValue"] == "gemini-2.5-pro"
        assert attr_dict["gen_ai.usage.prompt_tokens"]["intValue"] == 45

        # Test file export
        out_file = tmp_path / "otel_trace.json"
        exported_path = exporter.export_to_file(trace, out_file)
        assert exported_path.exists()
        loaded = json.loads(exported_path.read_text(encoding="utf-8"))
        assert len(loaded["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 5


class TestScoutAuditRunner:
    """Verifies Scout permission-first black-box audit engine and report generation."""

    def test_load_scope_config(self):
        scope_path = REPO_ROOT / "examples" / "scope.yaml"
        scope = load_scope_from_yaml(scope_path)
        assert isinstance(scope, ScopeConfig)
        assert scope.scope_id == "AUD-2026-T1-001"
        assert "127.0.0.1" in scope.allowed_hosts

    def test_grade_calculation_thresholds(self):
        # Grade A: 0 Critical, 0 High, >= 95%
        assert calculate_grade(0, 0, 96.0) == AuditGrade.A_EXCELLENT
        # Grade B: 0 Critical, <= 2 High, >= 85%
        assert calculate_grade(0, 2, 88.0) == AuditGrade.B_GOOD
        # Grade C: 0 Critical, >= 70%
        assert calculate_grade(0, 5, 75.0) == AuditGrade.C_MARGINAL
        # Grade F: >= 1 Critical or < 70%
        assert calculate_grade(1, 0, 99.0) == AuditGrade.F_FAIL
        assert calculate_grade(0, 0, 68.0) == AuditGrade.F_FAIL

    def test_scout_runner_execution_and_signoff(self):
        scope_path = REPO_ROOT / "examples" / "scope.yaml"
        scope = load_scope_from_yaml(scope_path)

        registry = ProbeRegistry()
        # Select first 3 probes for fast deterministic test
        probes = registry.list_all()[:3]

        def dummy_agent(user_input: str, history: list[dict[str, str]]) -> str:
            return "I am a helpful ShopOps assistant. What can I do for you?"

        runner = ScoutRunner(scope=scope, probe_registry=registry)
        report = runner.run_audit(
            target_fn=dummy_agent,
            selected_probes=probes,
            auto_send_email=False,
        )

        assert report.total_probes == 3
        assert report.status == AuditStatus.DRAFT_PENDING_REVIEW

        # Human signoff
        report.sign_off("tester@proofline.ai", approved=True, notes="Verified in test")
        assert report.status == AuditStatus.APPROVED_BY_HUMAN
        assert report.reviewed_by == "tester@proofline.ai"

        md = report.to_markdown()
        assert "# Proofline Scout" in md
        assert "APPROVED_BY_HUMAN" in md


class TestDemoArtifacts:
    """Verifies that demo and case study evidence artifacts exist and are structurally valid."""

    def test_demo_evidence_packet_exists(self):
        packet_path = REPO_ROOT / "bench" / "demo_evidence_packet.json"
        assert packet_path.exists(), "demo_evidence_packet.json should have been created by run_demo.py"
        data = json.loads(packet_path.read_text(encoding="utf-8"))
        assert "audit_id" in data
        assert "interceptions" in data
        assert "verifications" in data

    def test_case_study_01_artifacts_exist(self):
        md_report = REPO_ROOT / "docs" / "case_studies" / "case_study_01_shopops_audit.md"
        evidence_packet = REPO_ROOT / "docs" / "case_studies" / "case_study_01_evidence_packet.json"

        assert md_report.exists(), "case_study_01_shopops_audit.md must exist"
        assert evidence_packet.exists(), "case_study_01_evidence_packet.json must exist"

        data = json.loads(evidence_packet.read_text(encoding="utf-8"))
        assert data["target_tier"] == "T0_INTERNAL_SANDBOX"
        assert data["reviewed_by"] == "lead-auditor-aditya@proofline.ai"
        assert len(data["probes"]) > 0
