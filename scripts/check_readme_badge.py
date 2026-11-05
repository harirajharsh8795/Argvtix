"""
README Test Count Badge Validator.

Fails in CI if the badge in README.md does not match the actual number of collected pytest tests.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_actual_test_count() -> int:
    """Runs pytest --collect-only -q and parses total collected tests."""
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    # Match pattern: '(\d+) tests collected' or 'collected (\d+) items'
    match = re.search(r"(\d+)\s+tests collected", res.stdout)
    if not match:
        match = re.search(r"collected\s+(\d+)\s+items", res.stdout)
    if not match:
        raise ValueError(f"Could not parse test count from pytest output:\n{res.stdout}")
    return int(match.group(1))


def get_readme_badge_count() -> int:
    """Extracts test count number from README.md shield badge."""
    readme_path = REPO_ROOT / "README.md"
    content = readme_path.read_text(encoding="utf-8")
    match = re.search(r"tests-(\d+)%20passing", content)
    if not match:
        raise ValueError(f"Could not find tests-XXX%20passing badge in {readme_path}")
    return int(match.group(1))


def main() -> None:
    actual = get_actual_test_count()
    badge = get_readme_badge_count()

    print(f"Collected Tests:   {actual}")
    print(f"README Badge Count: {badge}")

    if actual != badge:
        print(
            f"ERROR: README badge test count mismatch! Badge has {badge}, but pytest collected {actual} tests.\n"
            f"Update README.md to match the real test count.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("SUCCESS: README badge matches collected test count exactly.")
    sys.exit(0)


if __name__ == "__main__":
    main()
