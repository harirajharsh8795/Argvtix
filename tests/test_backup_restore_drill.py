"""
Unit test for backup and restore disaster recovery drill (Weakness 15).
"""

from __future__ import annotations

from scripts.backup_restore_drill import run_drill


def test_backup_restore_drill_passes() -> None:
    result = run_drill("sqlite:///:memory:")
    assert result["status"] == "PASS"
    assert result["checksum_verified"] is True
    assert result["original_records"] == result["restored_records"]
    assert result["elapsed_ms"] > 0
