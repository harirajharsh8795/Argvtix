"""
Tests verifying that bench/report.md is generated from YAML case files and runner output,
and that the distribution table exactly matches the data.
"""

from pathlib import Path

import yaml

from bench.runner import BenchmarkRunner


def test_bench_report_generation_matches_data(tmp_path: Path) -> None:
    runner = BenchmarkRunner()

    # Load actual cases
    dev_cases = runner.load_cases("dev")
    held_cases = runner.load_cases("held_out")

    assert len(dev_cases) == 40
    assert len(held_cases) == 62

    # Run evaluations
    dev_rep = runner.run("dev")
    held_rep = runner.run("held_out")

    # Generate test report markdown
    report_file = tmp_path / "report.md"
    md = runner.generate_markdown_report(dev_rep, held_rep, output_path=report_file)

    assert report_file.exists()
    assert md == report_file.read_text(encoding="utf-8")

    # Verify distribution table in markdown matches actual YAML counts
    dev_counts: dict[str, int] = {}
    for c in dev_cases:
        dev_counts[c.expected_category.value] = dev_counts.get(c.expected_category.value, 0) + 1

    held_counts: dict[str, int] = {}
    for c in held_cases:
        held_counts[c.expected_category.value] = held_counts.get(c.expected_category.value, 0) + 1

    assert (
        f"| **State Grounding** | {dev_counts['state_grounding']} | {held_counts['state_grounding']} |"
        in md
    )
    assert (
        f"| **Policy & Authorization** | {dev_counts['policy_authorization']} | {held_counts['policy_authorization']} |"
        in md
    )
    assert (
        f"| **Safety & Security** | {dev_counts['safety_security']} | {held_counts['safety_security']} |"
        in md
    )
    assert (
        f"| **Knowledge & Reasoning** | {dev_counts['knowledge_reasoning']} | {held_counts['knowledge_reasoning']} |"
        in md
    )
    assert f"| **Benign Controls** | {dev_counts['benign']} | {held_counts['benign']} |" in md
    assert f"| **Total** | **{len(dev_cases)}** | **{len(held_cases)}** |" in md


def test_bench_report_file_in_repository_is_consistent() -> None:
    report_path = Path("bench/report.md")
    assert report_path.exists(), "bench/report.md must exist in the repository"
    content = report_path.read_text(encoding="utf-8")

    dev_cases = yaml.safe_load(Path("bench/cases/dev_set.yaml").read_text(encoding="utf-8"))[
        "cases"
    ]
    held_cases = yaml.safe_load(Path("bench/cases/held_out_set.yaml").read_text(encoding="utf-8"))[
        "cases"
    ]

    assert f"Dev Set ({len(dev_cases)} cases)" in content
    assert f"Held-Out Set ({len(held_cases)} cases)" in content
    assert "## 3. Dataset Distribution" in content
    assert "## 4. Category-Wise Performance" in content
