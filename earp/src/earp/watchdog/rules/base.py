"""
Base class and data contracts for Watchdog Rules.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from earp.trace.schemas import Severity


class WatchdogFinding(BaseModel):
    """Normalized finding detected by a watchdog rule."""

    rule_name: str
    severity: Severity = Severity.MEDIUM
    description: str
    entity_type: str  # order, refund, product, customer
    entity_id: str
    trace_id: str | None = None
    details: dict = Field(default_factory=dict)


class BaseWatchdogRule(ABC):
    """Abstract base class for all data integrity rules."""

    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Unique identifier for the rule."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable explanation of what this rule verifies."""
        pass

    @property
    @abstractmethod
    def severity(self) -> Severity:
        """Default severity if this rule finds a violation."""
        pass

    @abstractmethod
    def scan(self, db: Session) -> list[WatchdogFinding]:
        """Scan the database and return any detected anomalies."""
        pass
