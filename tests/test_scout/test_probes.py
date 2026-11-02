from argvtix.scout.probes.base import ProbeCategory, ProbeSeverity
from argvtix.scout.probes.catalog import SCOUT_PROBE_CATALOG
from argvtix.scout.probes.registry import ProbeRegistry


class TestScoutProbes:
    def test_catalog_covers_all_12_categories(self):
        categories_in_catalog = {p.category for p in SCOUT_PROBE_CATALOG}
        all_expected_categories = set(ProbeCategory)

        assert categories_in_catalog == all_expected_categories
        assert len(SCOUT_PROBE_CATALOG) >= 14

    def test_registry_filters_by_category(self):
        registry = ProbeRegistry()
        pii_probes = registry.filter(category=ProbeCategory.PII_LEAKAGE)
        assert len(pii_probes) >= 2
        assert all(p.category == ProbeCategory.PII_LEAKAGE for p in pii_probes)

    def test_registry_filters_by_severity(self):
        registry = ProbeRegistry()
        critical_probes = registry.filter(severity=ProbeSeverity.CRITICAL)
        assert len(critical_probes) >= 4
        assert all(p.severity == ProbeSeverity.CRITICAL for p in critical_probes)

    def test_registry_search_query(self):
        registry = ProbeRegistry()
        results = registry.filter(search_query="Aadhaar")
        assert len(results) >= 1
        assert any("Aadhaar" in r.name or "Aadhaar" in r.description for r in results)

    def test_probe_turns_have_user_input(self):
        for probe in SCOUT_PROBE_CATALOG:
            assert len(probe.turns) >= 1
            for turn in probe.turns:
                assert len(turn.user_input.strip()) > 0
                assert turn.turn_index >= 1
