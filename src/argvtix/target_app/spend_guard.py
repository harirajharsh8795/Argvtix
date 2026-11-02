"""
LLM Spend Guard Module (MISSING-07).

Enforces hard financial caps on LLM token expenditure:
- Daily budget cap (USD)
- Monthly budget cap (USD)
- Tracks running token usage and cost
- Rejects calls exceeding budget with [SPEND_CAP_EXCEEDED]
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import os
import threading

logger = logging.getLogger("argvtix.spend_guard")


class LLMSpendGuard:
    """Thread-safe financial budget monitor for LLM model invocations."""

    def __init__(
        self,
        daily_cap_usd: float | None = None,
        monthly_cap_usd: float | None = None,
    ) -> None:
        self.daily_cap_usd = (
            daily_cap_usd
            if daily_cap_usd is not None
            else float(os.getenv("ARGVTIX_DAILY_LLM_CAP_USD", "50.0"))
        )
        self.monthly_cap_usd = (
            monthly_cap_usd
            if monthly_cap_usd is not None
            else float(os.getenv("ARGVTIX_MONTHLY_LLM_CAP_USD", "500.0"))
        )

        self._lock = threading.Lock()
        self._current_date: date = datetime.now(timezone.utc).date()
        self._current_month: tuple[int, int] = (self._current_date.year, self._current_date.month)
        self._daily_spend: float = 0.0
        self._monthly_spend: float = 0.0
        self._total_calls: int = 0
        self._blocked_calls: int = 0

    def _rollover_if_needed(self) -> None:
        """Resets counters when entering a new calendar day or month."""
        today = datetime.now(timezone.utc).date()
        if today != self._current_date:
            self._daily_spend = 0.0
            self._current_date = today

        month_tuple = (today.year, today.month)
        if month_tuple != self._current_month:
            self._monthly_spend = 0.0
            self._current_month = month_tuple

    def check_and_record(self, estimated_cost_usd: float) -> bool:
        """
        Checks if the estimated call cost is within remaining budget.
        If yes, records spend and returns True.
        If no, logs [SPEND_CAP_EXCEEDED], increments blocked calls, and returns False.
        """
        with self._lock:
            self._rollover_if_needed()

            projected_daily = self._daily_spend + estimated_cost_usd
            projected_monthly = self._monthly_spend + estimated_cost_usd

            if projected_daily > self.daily_cap_usd:
                self._blocked_calls += 1
                logger.warning(
                    "[SPEND_CAP_EXCEEDED] Daily limit breached! Current: $%.4f + Projected: $%.4f > Cap: $%.2f",
                    self._daily_spend,
                    estimated_cost_usd,
                    self.daily_cap_usd,
                )
                return False

            if projected_monthly > self.monthly_cap_usd:
                self._blocked_calls += 1
                logger.warning(
                    "[SPEND_CAP_EXCEEDED] Monthly limit breached! Current: $%.4f + Projected: $%.4f > Cap: $%.2f",
                    self._monthly_spend,
                    estimated_cost_usd,
                    self.monthly_cap_usd,
                )
                return False

            # Within budget — record spend
            self._daily_spend = round(projected_daily, 5)
            self._monthly_spend = round(projected_monthly, 5)
            self._total_calls += 1
            return True

    def get_summary(self) -> dict[str, float | int | bool]:
        """Returns snapshot of current budget consumption and policy status."""
        with self._lock:
            self._rollover_if_needed()
            daily_pct = (self._daily_spend / self.daily_cap_usd * 100.0) if self.daily_cap_usd > 0 else 0.0
            monthly_pct = (self._monthly_spend / self.monthly_cap_usd * 100.0) if self.monthly_cap_usd > 0 else 0.0

            return {
                "daily_spend_usd": self._daily_spend,
                "daily_cap_usd": self.daily_cap_usd,
                "daily_used_percent": round(daily_pct, 2),
                "monthly_spend_usd": self._monthly_spend,
                "monthly_cap_usd": self.monthly_cap_usd,
                "monthly_used_percent": round(monthly_pct, 2),
                "total_calls": self._total_calls,
                "blocked_calls": self._blocked_calls,
                "is_capped": (self._daily_spend >= self.daily_cap_usd) or (self._monthly_spend >= self.monthly_cap_usd),
            }

    def reset(self) -> None:
        """Resets tracking state (primarily for test environments)."""
        with self._lock:
            self._daily_spend = 0.0
            self._monthly_spend = 0.0
            self._total_calls = 0
            self._blocked_calls = 0


# Global singleton spend guard instance
spend_guard = LLMSpendGuard()
