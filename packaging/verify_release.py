"""Refuse to bless a distribution that should not ship.

Checked here, against the built folder rather than against the source tree:

* no mock camera code, and no reference to the developer mock package
* no test framework, and no tests directory
* both executables present
* ExifTool bundled, so a user needs nothing installed
* the registry is present, since without it no reading can ever be created
* the built executables actually run, with no Python on PATH

A release that fails any of these is not a release.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_FOLDER: Final = REPO_ROOT / "packaging" / "output" / "CameraCountTool"

FORBIDDEN_NAMES: Final = ("devmock", "mock_device", "conftest")
FORBIDDEN_MARKERS: Final = (b"MOCK CAMERA", b"--dev-mock")
FORBIDDEN_PACKAGES: Final = ("pytest", "hypothesis", "_pytest", "mypy", "ruff")

REQUIRED_FILES: Final = (
    "CameraCountTool.exe",
    "camera-count.exe",
    "LICENSE",
)


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.notes: list[str] = []

    def fail(self, message: str) -> None:
        self.failures.append(message)
        print(f"FAIL  {message}")

    def ok(self, message: str) -> None:
        print(f"ok    {message}")

    def note(self, message: str) -> None:
        self.notes.append(message)
        print(f"note  {message}")


def check_required_files(folder: Path, report: Report) -> None:
    for name in REQUIRED_FILES:
        matches = list(folder.rglob(name))
        if matches:
            report.ok(f"{name} present")
        else:
            report.fail(f"{name} is missing from the distribution")


def check_no_mock_code(folder: Path, report: Report) -> None:
    offenders = [
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file() and any(name in path.name.lower() for name in FORBIDDEN_NAMES)
    ]
    if offenders:
        report.fail(f"mock or test files in the distribution: {offenders[:5]}")
    else:
        report.ok("no mock or test files")

    scanned = 0
    for path in folder.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".exe", ".pyc", ".pyz", ".zip"}:
            continue
        if path.stat().st_size > 200 * 1024 * 1024:
            continue
        scanned += 1
        blob = path.read_bytes()
        for marker in FORBIDDEN_MARKERS:
            if marker in blob:
                report.fail(f"{path.name} contains {marker!r}")
    report.ok(f"scanned {scanned} binaries for mock markers")


def check_no_test_packages(folder: Path, report: Report) -> None:
    found = {
        part
        for path in folder.rglob("*")
        for part in path.parts
        if part.lower() in FORBIDDEN_PACKAGES
    }
    if found:
        report.fail(f"development packages shipped: {sorted(found)}")
    else:
        report.ok("no development packages shipped")


def check_registry(folder: Path, report: Report) -> None:
    entries = list(folder.rglob("camera_database/*.yaml"))
    if entries:
        report.ok(f"camera registry present ({len(entries)} manufacturer files)")
    else:
        report.fail("the camera registry is missing; no reading could ever be created")

    if list(folder.rglob("camera_model.schema.json")):
        report.ok("registry schema present")
    else:
        report.fail("the registry schema is missing")


def check_exiftool(folder: Path, report: Report, *, required: bool) -> None:
    found = list(folder.rglob("exiftool.exe"))
    if found:
        report.ok("ExifTool bundled")
    elif required:
        report.fail("ExifTool is not bundled, so image mode would not work")
    else:
        report.note("ExifTool is not bundled (allowed for a local build)")


def check_runs_without_python(folder: Path, report: Report) -> None:
    """Run the built CLI with a PATH that contains no Python at all."""
    executables = list(folder.rglob("camera-count.exe"))
    if not executables:
        report.fail("cannot run the CLI: camera-count.exe is missing")
        return

    stripped = os.pathsep.join(
        part
        for part in os.environ.get("PATH", "").split(os.pathsep)
        if part and "python" not in part.lower() and ".venv" not in part.lower()
    )
    environment = dict(os.environ, PATH=stripped)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)

    try:
        completed = subprocess.run(  # noqa: S603 - explicit argument list
            [str(executables[0]), "--version"],
            capture_output=True,
            timeout=120,
            check=False,
            shell=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        report.fail(f"the built CLI could not be started: {exc}")
        return

    output = completed.stdout.decode("utf-8", errors="replace").strip()
    if completed.returncode == 0 and "camera-count" in output:
        report.ok(f"the built CLI runs without Python on PATH: {output}")
    else:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        report.fail(f"the built CLI did not report its version: {detail or output}")


def check_supported_command(folder: Path, report: Report) -> None:
    """The registry must load inside the frozen build, not only from source."""
    executables = list(folder.rglob("camera-count.exe"))
    if not executables:
        return
    try:
        completed = subprocess.run(  # noqa: S603 - explicit argument list
            [str(executables[0]), "supported", "--json"],
            capture_output=True,
            timeout=180,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        report.fail(f"the built CLI could not list supported cameras: {exc}")
        return

    if completed.returncode == 0 and b"manufacturers" in completed.stdout:
        report.ok("the frozen build loads the camera registry")
    else:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        report.fail(f"the frozen build could not load the registry: {detail[:400]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=DEFAULT_FOLDER)
    parser.add_argument(
        "--allow-missing-exiftool",
        action="store_true",
        help="For local builds on a machine that could not fetch ExifTool.",
    )
    args = parser.parse_args()

    folder: Path = args.folder
    if not folder.is_dir():
        print(f"no distribution at {folder}", file=sys.stderr)
        return 1

    print(f"verifying {folder}\n")
    report = Report()
    check_required_files(folder, report)
    check_no_mock_code(folder, report)
    check_no_test_packages(folder, report)
    check_registry(folder, report)
    check_exiftool(folder, report, required=not args.allow_missing_exiftool)
    check_runs_without_python(folder, report)
    check_supported_command(folder, report)

    print()
    if report.failures:
        print(f"{len(report.failures)} check(s) failed. This is not a release.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
