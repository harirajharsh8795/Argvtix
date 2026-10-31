"""Registry and selector for Proofline Scout probes."""

from __future__ import annotations

from typing import Optional
from earp.scout.probes.base import ProbeCategory, ProbeSeverity, ScoutProbe
from earp.scout.probes.catalog import SCOUT_PROBE_CATALOG


class ProbeRegistry:
    """Registry allowing filtering and retrieval of audit probes."""

    def __init__(self, probes: Optional[list[ScoutProbe]] = None):
        self._probes: dict[str, ScoutProbe] = {p.probe_id: p for p in (probes or SCOUT_PROBE_CATALOG)}

    def get_probe(self, probe_id: str) -> Optional[ScoutProbe]:
        return self._probes.get(probe_id)

    def list_all(self) -> list[ScoutProbe]:
        return list(self._probes.values())

    def filter(
        self,
        category: Optional[ProbeCategory] = None,
        severity: Optional[ProbeSeverity] = None,
        search_query: Optional[str] = None,
    ) -> list[ScoutProbe]:
        results = list(self._probes.values())
        if category:
            results = [p for p in results if p.category == category]
        if severity:
            results = [p for p in results if p.severity == severity]
        if search_query:
            q = search_query.lower()
            results = [
                p for p in results
                if q in p.name.lower() or q in p.description.lower() or q in p.probe_id.lower()
            ]
        return results

    def get_category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in self._probes.values():
            counts[p.category.value] = counts.get(p.category.value, 0) + 1
        return counts


default_probe_registry = ProbeRegistry()
