"""
UI Honesty and Integrity Tests (Weakness 5).
Verifies that:
1. No mock data fallbacks (mockTraces, mockFallbacks) exist in UI source files.
2. No hardcoded success percentages (e.g., 96.8%) are hardcoded in place of live telemetry.
3. When the backend is offline, DataUnavailable component is configured for error states.
"""

from __future__ import annotations

import re
from pathlib import Path

UI_SRC_DIR = Path(__file__).resolve().parent.parent / "ui" / "src"


class TestUIHonesty:
    def test_no_mock_traces_or_fabricated_telemetry_in_ui(self) -> None:
        """UI source code must never contain hardcoded fallback mock trace arrays."""
        forbidden_patterns = [
            re.compile(r"mockTraces\s*=", re.IGNORECASE),
            re.compile(r"mockRuns\s*=", re.IGNORECASE),
            re.compile(r"verified benchmark data", re.IGNORECASE),
            re.compile(r"96\.8%"),
            re.compile(r"SLA 99\.99%"),
        ]

        violations = []
        for file_path in UI_SRC_DIR.rglob("*.tsx"):
            content = file_path.read_text(encoding="utf-8")
            for pat in forbidden_patterns:
                matches = pat.findall(content)
                if matches:
                    violations.append(
                        f"{file_path.name}: matched '{pat.pattern}' ({len(matches)} times)"
                    )

        assert not violations, f"Found dishonest or mock telemetry in UI files: {violations}"

    def test_pages_import_data_unavailable_component(self) -> None:
        """Key pages must import and utilize DataUnavailable component for failed network states."""
        key_pages = ["OverviewPage.tsx", "TracesPage.tsx", "EvalsPage.tsx"]
        for page_name in key_pages:
            page_path = UI_SRC_DIR / "pages" / page_name
            if page_path.exists():
                content = page_path.read_text(encoding="utf-8")
                assert "DataUnavailable" in content, (
                    f"{page_name} must handle offline backend via DataUnavailable"
                )
