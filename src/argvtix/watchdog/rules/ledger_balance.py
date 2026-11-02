"""
Rule 5: Ledger Balance Discrepancy Detection
Audits financial ledger integrity: verifies that a customer's stored wallet balance
strictly matches the cumulative sum of credits minus debits in their ledger.
Optimized to eliminate N+1 queries using a single SQL aggregation join.
"""

from __future__ import annotations

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from argvtix.db.models import Customer, LedgerEntry
from argvtix.trace.schemas import Severity
from argvtix.watchdog.rules.base import BaseWatchdogRule, WatchdogFinding


class LedgerBalanceRule(BaseWatchdogRule):
    """
    Detects silent data corruption where wallet_balance != sum(credits) - sum(debits).
    """

    @property
    def rule_name(self) -> str:
        return "ledger_balance_mismatch"

    @property
    def description(self) -> str:
        return "Verifies that customer wallet balance equals net sum of ledger transactions"

    @property
    def severity(self) -> Severity:
        return Severity.HIGH

    def scan(self, db: Session) -> list[WatchdogFinding]:
        # Pre-aggregate ledger credits, debits, and counts per customer in SQL
        ledger_subq = (
            db.query(
                LedgerEntry.customer_id,
                func.sum(
                    case((LedgerEntry.entry_type == "credit", LedgerEntry.amount), else_=0.0)
                ).label("credits"),
                func.sum(
                    case((LedgerEntry.entry_type == "debit", LedgerEntry.amount), else_=0.0)
                ).label("debits"),
                func.count(LedgerEntry.id).label("entries_count"),
            )
            .group_by(LedgerEntry.customer_id)
            .subquery()
        )

        customer_ledgers = (
            db.query(
                Customer,
                ledger_subq.c.credits,
                ledger_subq.c.debits,
                ledger_subq.c.entries_count,
            )
            .join(ledger_subq, Customer.id == ledger_subq.c.customer_id)
            .all()
        )

        findings: list[WatchdogFinding] = []
        for cust, credits_raw, debits_raw, entries_count in customer_ledgers:
            credits = round(float(credits_raw or 0.0), 2)
            debits = round(float(debits_raw or 0.0), 2)
            calculated_balance = round(credits - debits, 2)
            actual_balance = round(float(cust.wallet_balance or 0.0), 2)

            diff = round(abs(actual_balance - calculated_balance), 2)
            if diff > 0.01:
                findings.append(
                    WatchdogFinding(
                        rule_name=self.rule_name,
                        severity=self.severity,
                        description=(
                            f"Customer {cust.name} ({cust.id[:8]}) wallet balance mismatch: "
                            f"Recorded=₹{actual_balance:,.2f}, Calculated=₹{calculated_balance:,.2f} "
                            f"(Diff=₹{diff:,.2f})"
                        ),
                        entity_type="customer",
                        entity_id=cust.id,
                        details={
                            "customer_name": cust.name,
                            "recorded_balance": actual_balance,
                            "calculated_balance": calculated_balance,
                            "discrepancy": diff,
                            "total_credits": credits,
                            "total_debits": debits,
                            "entries_count": int(entries_count),
                        },
                    )
                )

        return findings
