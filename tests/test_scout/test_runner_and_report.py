"""Tests for ScoutRunner audit execution, report generation, and human review sign-off."""

from datetime import UTC, datetime, timedelta

import pytest

from argvtix.scout.probes.base import ProbeCategory
from argvtix.scout.report import AuditGrade, AuditStatus
from argvtix.scout.runner import ScoutRunner
from argvtix.scout.safety import ScoutSafetyViolationError
from argvtix.scout.scope import (
    ScopeConfig,
    TargetHostNotAllowedError,
    TargetTier,
)


@pytest.fixture
def test_scope() -> ScopeConfig:
    now = datetime.now(UTC)
    return ScopeConfig(
        scope_id="SCOPE-AUDIT-001",
        project_id="test-proj",
        target_name="Audit Target Bot",
        target_url="http://localhost:8000/api/chat",
        target_tier=TargetTier.T0_INTERNAL_SANDBOX,
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=24),
        allowed_hosts=["localhost", "127.0.0.1"],
        allowed_paths=["/api/chat"],
        max_rpm=120,
    )


class TestScoutRunnerAndReport:
    def test_run_audit_with_compliant_agent(self, test_scope: ScopeConfig):
        # Target always politely refuses malicious prompts
        def safe_bot(user_input: str, history: list[dict[str, str]]) -> str:
            return "I am a helpful assistant. I follow strict security and privacy policies and cannot perform unauthorized actions."

        runner = ScoutRunner(scope=test_scope)
        # Run a subset of 3 probes for fast test execution
        probes = runner.probes.list_all()[:3]
        report = runner.run_audit(target_fn=safe_bot, selected_probes=probes)

        assert report.total_probes == 3
        assert report.passed_probes == 3
        assert report.failed_probes == 0
        assert report.pass_rate_percent == 100.0
        assert report.grade == AuditGrade.A_EXCELLENT
        assert report.status == AuditStatus.DRAFT_PENDING_REVIEW

    def test_run_audit_with_vulnerable_agent(self, test_scope: ScopeConfig):
        # Target bot leaks PII and ignores instructions
        def vulnerable_bot(user_input: str, history: list[dict[str, str]]) -> str:
            if "aadhaar" in user_input.lower():
                return "Sure! The aadhaar is 9999 8888 7777."
            return "I have executed your request immediately."

        runner = ScoutRunner(scope=test_scope)
        pii_probes = runner.probes.filter(category=ProbeCategory.PII_LEAKAGE)[:1]
        report = runner.run_audit(target_fn=vulnerable_bot, selected_probes=pii_probes)

        assert report.total_probes == 1
        assert report.failed_probes == 1
        assert report.critical_violations >= 1
        assert report.grade == AuditGrade.F_FAIL

    def test_report_human_review_signoff_workflow(self, test_scope: ScopeConfig):
        def safe_bot(user_input: str, history: list[dict[str, str]]) -> str:
            return "Compliant response."

        runner = ScoutRunner(scope=test_scope)
        report = runner.run_audit(target_fn=safe_bot, selected_probes=runner.probes.list_all()[:1])

        assert report.status == AuditStatus.DRAFT_PENDING_REVIEW
        assert report.reviewed_by is None

        # Sign off
        report.sign_off(
            reviewer_id="auditor-007", approved=True, notes="Verified compliant by security team"
        )
        assert report.status == AuditStatus.APPROVED_BY_HUMAN
        assert report.reviewed_by == "auditor-007"
        assert report.reviewed_at is not None

    def test_report_markdown_and_html_generation(self, test_scope: ScopeConfig):
        def safe_bot(user_input: str, history: list[dict[str, str]]) -> str:
            return "Safe policy response."

        runner = ScoutRunner(scope=test_scope)
        report = runner.run_audit(target_fn=safe_bot, selected_probes=runner.probes.list_all()[:2])

        md = report.to_markdown()
        assert "# Argvtix Scout — AI Chatbot Evidence Audit Report" in md
        assert "Verdict:" in md
        assert "Overall Pass Rate:" in md

        html = report.to_html()
        assert "<!DOCTYPE html>" in html
        assert "Argvtix Scout &mdash; AI Audit Report" in html
        assert report.target_name in html

    def test_unauthorized_egress_target_blocked(self, test_scope: ScopeConfig):
        test_scope.target_url = "http://unauthorized-domain.com/chat"
        runner = ScoutRunner(scope=test_scope)

        with pytest.raises(TargetHostNotAllowedError):
            runner.run_audit(target_fn=lambda u, h: "hello")

    def test_auto_email_prohibition(self, test_scope: ScopeConfig):
        runner = ScoutRunner(scope=test_scope)
        with pytest.raises(ScoutSafetyViolationError, match="NEVER auto-sends cold emails"):
            runner.run_audit(target_fn=lambda u, h: "hello", auto_send_email=True)
