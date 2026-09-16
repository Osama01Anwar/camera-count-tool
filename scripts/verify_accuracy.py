"""Check the installed tool's numbers against ExifTool's own output.

This is the test that matters most and the one a unit test cannot do: it runs
the **installed** ``camera-count`` exactly as a user would, then asks ExifTool
directly about the same file and compares. ExifTool is the ground truth because
it is the source the registry cites.

It asserts two things, the second more important than the first:

1. Every number the tool prints equals the value of the field it cites.
2. The tool prints no number for a file that failed the originality checks or
   for a model with no registered method.

Usage:

    python scripts/verify_accuracy.py PHOTO.NEF [MORE ...]
    python scripts/verify_accuracy.py --samples        # the ExifTool samples

Point it at your own camera files. A file straight off the memory card is the
most useful thing you can give it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
VENDOR: Final = REPO_ROOT / "packaging" / "vendor"

HEDGING: Final = ("approx", "probab", "confidence", "likely")


def find_cli(override: str | None = None) -> list[str]:
    """Prefer an installed camera-count; fall back to running from source.

    Pass ``--cli`` to point at a specific build. Worth doing deliberately: an
    installed copy on PATH can easily be older than the checkout you are
    sitting in, and then this script quietly verifies the wrong program.
    """
    if override:
        return [override]
    found = shutil.which("camera-count")
    if found:
        return [found]
    return [sys.executable, "-m", "camera_count.cli.main"]


def find_exiftool() -> list[str] | None:
    """The same ExifTool the tool would use, for an independent second opinion."""
    override = os.environ.get("CAMERA_COUNT_EXIFTOOL")
    candidates = [Path(override)] if override else []
    candidates.append(VENDOR / "exiftool" / "exiftool.exe")
    found = shutil.which("exiftool")
    if found:
        candidates.append(Path(found))
    candidates.extend(sorted(VENDOR.glob("exiftool-*/exiftool")))

    for candidate in candidates:
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() == ".exe":
            return [str(candidate)]
        perl = shutil.which("perl") or r"C:\Program Files\Git\usr\bin\perl.exe"
        if Path(perl).is_file():
            return [perl, str(candidate)]
    return None


def sample_files() -> list[Path]:
    directories = sorted(VENDOR.glob("exiftool-*/t/images"))
    if not directories:
        raise SystemExit(
            "no ExifTool samples found. Run:\n  python scripts/fetch_exiftool.py --mode source"
        )
    return sorted(
        path
        for path in directories[-1].iterdir()
        if path.suffix.lower()
        in {".jpg", ".jpeg", ".nef", ".cr2", ".cr3", ".arw", ".raf", ".orf", ".rw2", ".pef"}
    )


def run_tool(cli: list[str], path: Path) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603 - explicit argument list
        [*cli, "exif", str(path), "--json"],
        capture_output=True,
        check=False,
        shell=False,
    )
    text = completed.stdout.decode("utf-8", errors="replace")
    try:
        parsed: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        return {"__error__": (text or stderr).strip()[:300]}
    return parsed


def run_exiftool(command: list[str], path: Path) -> dict[str, Any]:
    completed = subprocess.run(  # noqa: S603 - explicit argument list
        [*command, "-j", "-n", "-G1", "-a", "-u", str(path)],
        capture_output=True,
        check=False,
        shell=False,
    )
    try:
        documents = json.loads(completed.stdout.decode("utf-8", errors="replace") or "[]")
    except json.JSONDecodeError:
        return {}
    first: dict[str, Any] = documents[0] if documents else {}
    return first


def check_file(cli: list[str], exiftool: list[str], path: Path) -> list[str]:
    problems: list[str] = []
    ours = run_tool(cli, path)
    if "__error__" in ours:
        return [f"{path.name}: the tool produced no JSON: {ours['__error__']}"]

    entry = ours["files"][0]
    truth = run_exiftool(exiftool, path)
    reported = [counter for counter in entry["counters"] if counter["available"]]

    for counter in reported:
        identifier = counter["identifier"]
        expected = truth.get(identifier)
        actual = counter["value"]
        if expected is None:
            problems.append(
                f"{path.name}: reported {actual} citing {identifier}, which ExifTool "
                "does not report for this file"
            )
        elif int(expected) != int(actual):
            problems.append(
                f"{path.name}: reported {actual} but ExifTool says {expected} for {identifier}"
            )
        else:
            print(f"ok    {path.name}: {counter['counter']} = {actual} (matches {identifier})")
            print(f"      cited: {counter['citation']}")

    if reported and not entry["is_original"]:
        problems.append(
            f"{path.name}: reported a count from a file that failed the originality checks"
        )

    if not reported:
        state = "original" if entry["is_original"] else "not an original"
        print(f"ok    {path.name}: no count reported ({state})")

    blob = json.dumps(entry).lower()
    problems.extend(
        f"{path.name}: output contains hedging vocabulary {term!r}"
        for term in HEDGING
        if term in blob
    )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, help="Camera files to check.")
    parser.add_argument(
        "--samples",
        action="store_true",
        help="Check the sample images from the ExifTool distribution.",
    )
    parser.add_argument(
        "--cli",
        help="Path to the camera-count executable to verify. Defaults to PATH.",
    )
    args = parser.parse_args()

    paths = list(args.files)
    if args.samples:
        paths.extend(sample_files())
    if not paths:
        parser.error("give at least one file, or --samples")

    cli = find_cli(args.cli)
    exiftool = find_exiftool()
    if exiftool is None:
        raise SystemExit(
            "ExifTool was not found, so there is nothing to compare against. "
            "Run scripts/fetch_exiftool.py, or install ExifTool."
        )

    print(f"tool:     {' '.join(cli)}")
    print(f"exiftool: {' '.join(exiftool)}")
    print()

    problems: list[str] = []
    for path in paths:
        if not path.is_file():
            print(f"skip  {path}: not a file")
            continue
        problems.extend(check_file(cli, exiftool, path))

    print()
    if problems:
        print(f"{len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Every number printed matches its cited source, and no number was printed")
    print("that could not be justified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
