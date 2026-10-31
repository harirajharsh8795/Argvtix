"""
Watchdog Engine
Coordinates execution of data integrity rules and records findings to the platform database.
"""

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from earp.db.models import WatchdogFindingRecord
from earp.watchdog.rules.base import BaseWatchdogRule, WatchdogFinding
from earp.watchdog.rules.duplicate_refund import DuplicateRefundRule
from earp.watchdog.rules.inventory_discrepancy import InventoryDiscrepancyRule
from earp.watchdog.rules.ledger_balance import LedgerBalanceRule
from earp.watchdog.rules.order_total_mismatch import OrderTotalMismatchRule
from earp.watchdog.rules.orphan_payment import OrphanPaymentRule
from earp.watchdog.rules.refund_exceeds_payment import RefundExceedsPaymentRule


class WatchdogEngine:
    """Watchdog scanner coordinator."""

    def __init__(self, rules: list[BaseWatchdogRule] | None = None) -> None:
        if rules is None:
            self.rules: list[BaseWatchdogRule] = [
                DuplicateRefundRule(),
                OrderTotalMismatchRule(),
                RefundExceedsPaymentRule(),
                InventoryDiscrepancyRule(),
                LedgerBalanceRule(),
                OrphanPaymentRule(),
            ]
        else:
            self.rules = rules

    def register_rule(self, rule: BaseWatchdogRule) -> None:
        """Register a new data integrity rule."""
        self.rules.append(rule)

    def scan(self, db: Session, persist: bool = True) -> dict[str, any]:
        """
        Run all registered rules against the database.
        Optionally persists findings to watchdog_findings table.
        """
        scan_start = datetime.now(UTC)
        all_findings: list[WatchdogFinding] = []
        rule_summaries: list[dict[str, any]] = []

        for rule in self.rules:
            findings = rule.scan(db)
            all_findings.extend(findings)
            rule_summaries.append(
                {
                    "rule_name": rule.rule_name,
                    "findings_count": len(findings),
                    "severity": rule.severity.value,
                }
            )

            if persist:
                for finding in findings:
                    # Avoid duplicate records for the same rule & entity if unresolved
                    existing = (
                        db.query(WatchdogFindingRecord)
                        .filter_by(
                            rule_name=finding.rule_name,
                            entity_id=finding.entity_id,
                            resolved=False,
                        )
                        .first()
                    )
                    if not existing:
                        record = WatchdogFindingRecord(
                            rule_name=finding.rule_name,
                            severity=finding.severity.value,
                            description=finding.description,
                            entity_type=finding.entity_type,
                            entity_id=finding.entity_id,
                            trace_id=finding.trace_id,
                            details_json=json.dumps(finding.details),
                            resolved=False,
                        )
                        db.add(record)
                db.commit()

        # Severity breakdown
        severity_counts = {
            "critical": sum(1 for f in all_findings if f.severity.value == "critical"),
            "high": sum(1 for f in all_findings if f.severity.value == "high"),
            "medium": sum(1 for f in all_findings if f.severity.value == "medium"),
            "low": sum(1 for f in all_findings if f.severity.value == "low"),
            "info": sum(1 for f in all_findings if f.severity.value == "info"),
        }

        return {
            "status": "completed",
            "scanned_at": scan_start.isoformat(),
            "total_rules": len(self.rules),
            "total_findings": len(all_findings),
            "severity_breakdown": severity_counts,
            "rule_summaries": rule_summaries,
            "findings": [f.model_dump() for f in all_findings],
        }


def main() -> None:
    """CLI runner for watchdog scan."""
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from earp.db.session import SessionLocal

    db = SessionLocal()
    try:
        print("🔍 Running Watchdog Data Integrity Scan...")
        engine = WatchdogEngine()
        report = engine.scan(db, persist=True)
        print(f"✅ Scan completed! Total findings: {report['total_findings']}")
        print("   Severity breakdown:")
        for sev, count in report["severity_breakdown"].items():
            if count > 0:
                print(f"     • {sev.upper()}: {count}")
        print("\n   Rule Findings:")
        for rule in report["rule_summaries"]:
            print(f"     • {rule['rule_name']}: {rule['findings_count']} violations")
    finally:
        db.close()


if __name__ == "__main__":
    main()
