"""Fail the build when the parts that must not be wrong are under-tested.

The target is not a single repository-wide number. Coverage matters most in the
code that decides whether a number is shown at all, so each of those packages
carries its own floor.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Final

#: package prefix -> minimum percentage of lines covered
FLOORS: Final[dict[str, float]] = {
    "camera_count/core": 90.0,
    "camera_count/ptp": 85.0,
    "camera_count/adapters": 85.0,
    "camera_count/metadata": 85.0,
    "camera_count/registry": 85.0,
}


def coverage_by_prefix(report: Path) -> dict[str, tuple[int, int]]:
    """Return {prefix: (covered_lines, total_lines)}."""
    tree = ElementTree.parse(report)
    totals: dict[str, tuple[int, int]] = dict.fromkeys(FLOORS, (0, 0))

    for class_element in tree.iter("class"):
        filename = (class_element.get("filename") or "").replace("\\", "/")
        for prefix in FLOORS:
            if prefix in filename:
                covered, total = totals[prefix]
                for line in class_element.iter("line"):
                    total += 1
                    if (line.get("hits") or "0") != "0":
                        covered += 1
                totals[prefix] = (covered, total)
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="coverage.xml")
    args = parser.parse_args()

    if not args.report.is_file():
        print(f"no coverage report at {args.report}", file=sys.stderr)
        return 1

    totals = coverage_by_prefix(args.report)
    failures: list[str] = []

    for prefix, floor in sorted(FLOORS.items()):
        covered, total = totals[prefix]
        if total == 0:
            failures.append(f"{prefix}: no lines were measured at all")
            print(f"FAIL  {prefix}: nothing measured")
            continue
        percentage = 100.0 * covered / total
        marker = "ok  " if percentage >= floor else "FAIL"
        print(f"{marker}  {prefix}: {percentage:.1f}% of {total} lines (floor {floor:.0f}%)")
        if percentage < floor:
            failures.append(f"{prefix}: {percentage:.1f}% is below {floor:.0f}%")

    if failures:
        print("\nCoverage floors not met:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nEvery coverage floor is met.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
