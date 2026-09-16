"""Running ExifTool safely.

ExifTool is invoked as a separate process with an explicit argument list -
never a shell - under a timeout, and it is only ever asked to read. Arguments
are passed through an argument file encoded as UTF-8 together with
``-charset filename=utf8``, which is ExifTool's documented way to handle paths
Windows would otherwise mangle.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from camera_count.core.errors import MetadataError, ToolNotFoundError

#: Environment variable that overrides discovery.
EXIFTOOL_ENV: Final = "CAMERA_COUNT_EXIFTOOL"

#: Largest file this program will hand to ExifTool (512 MiB).
MAX_FILE_BYTES: Final = 512 * 1024 * 1024

#: Largest JSON answer accepted back (64 MiB).
MAX_OUTPUT_BYTES: Final = 64 * 1024 * 1024

DEFAULT_TIMEOUT_SECONDS: Final = 60

#: -j JSON, -n numeric values, -G1 family-1 group names, -a all tags including
#: duplicates, -u unknown tags. Group names matter: a registry identifier is
#: "Group:Tag", so it can only be matched when groups are present.
READ_ARGUMENTS: Final[tuple[str, ...]] = ("-j", "-n", "-G1", "-a", "-u")


#: Places a Perl interpreter is commonly found on Windows. Only used when
#: ExifTool was located as a Perl script rather than as a packaged .exe.
PERL_CANDIDATES: Final[tuple[str, ...]] = (
    r"C:\Strawberry\perl\bin\perl.exe",
    r"C:\Program Files\Git\usr\bin\perl.exe",
    r"C:\Program Files (x86)\Git\usr\bin\perl.exe",
)


@dataclass(frozen=True, slots=True)
class ExifToolInfo:
    """Where ExifTool came from and which version it is."""

    executable: Path
    version: str
    bundled: bool
    interpreter: Path | None = None

    def describe(self) -> str:
        origin = "bundled" if self.bundled else "system"
        via = f" via {self.interpreter}" if self.interpreter else ""
        return f"ExifTool {self.version} ({origin}: {self.executable}{via})"


def _frozen_root() -> Path | None:
    """The directory of a PyInstaller bundle, when running from one."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def _candidate_paths() -> list[Path]:
    candidates: list[Path] = []

    override = os.environ.get(EXIFTOOL_ENV)
    if override:
        candidates.append(Path(override))

    root = _frozen_root()
    if root is not None:
        candidates.append(root / "exiftool" / "exiftool.exe")
        candidates.append(root / "exiftool.exe")

    # A source checkout that has run scripts/fetch_exiftool.py.
    vendor = Path(__file__).resolve().parents[3] / "packaging" / "vendor"
    candidates.append(vendor / "exiftool" / "exiftool.exe")

    # A real executable beats a script that needs an interpreter, so anything
    # on PATH comes before the Perl distribution.
    found = shutil.which("exiftool")
    if found:
        candidates.append(Path(found))

    # The Perl distribution, for development machines that have Perl.
    candidates.extend(sorted(vendor.glob("exiftool-*/exiftool")))

    return candidates


def find_exiftool() -> Path:
    """Locate ExifTool, or say clearly that there is none."""
    for candidate in _candidate_paths():
        if candidate.is_file():
            return candidate
    raise ToolNotFoundError(
        "ExifTool was not found. The packaged release bundles it; a source "
        "install needs exiftool on PATH, or the "
        f"{EXIFTOOL_ENV} environment variable pointing at exiftool.exe."
    )


def find_perl() -> Path | None:
    """Locate a Perl interpreter, for a Perl-script ExifTool."""
    found = shutil.which("perl")
    if found:
        return Path(found)
    for candidate in PERL_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def build_command(executable: Path) -> list[str]:
    """Build the command prefix for this ExifTool.

    A packaged ``exiftool.exe`` runs directly. The Perl distribution ships a
    script with no extension, which needs an interpreter.
    """
    if executable.suffix.lower() == ".exe":
        return [str(executable)]
    perl = find_perl()
    if perl is None:
        raise ToolNotFoundError(
            f"{executable} is a Perl script and no Perl interpreter was found. "
            "Use the packaged release, which bundles a self-contained ExifTool."
        )
    return [str(perl), str(executable)]


def exiftool_info(executable: Path | None = None) -> ExifToolInfo:
    """Ask ExifTool for its version."""
    exe = executable or find_exiftool()
    command = build_command(exe)
    completed = _run([*command, "-ver"], timeout=30)
    version = completed.strip() or "unknown"
    return ExifToolInfo(
        executable=exe,
        version=version,
        bundled=_frozen_root() is not None,
        interpreter=Path(command[0]) if len(command) > 1 else None,
    )


def _run(command: Sequence[str], *, timeout: int) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - explicit argument list, never a shell
            list(command),
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise ToolNotFoundError(f"could not start ExifTool: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MetadataError(f"ExifTool did not finish within {timeout}s") from exc

    if len(completed.stdout) > MAX_OUTPUT_BYTES:
        raise MetadataError("ExifTool returned more data than this program will read")

    if completed.returncode != 0 and not completed.stdout:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise MetadataError(f"ExifTool failed: {detail or completed.returncode}")

    return completed.stdout.decode("utf-8", errors="replace")


def check_readable(path: Path) -> Path:
    """Validate a path before anything is run against it."""
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_file():
        raise MetadataError(f"not a file: {path}")
    size = resolved.stat().st_size
    if size == 0:
        raise MetadataError(f"file is empty: {path}")
    if size > MAX_FILE_BYTES:
        raise MetadataError(
            f"file is larger than the {MAX_FILE_BYTES} byte limit: {path} ({size} bytes)"
        )
    # Opening read-only confirms the permission before ExifTool is started, and
    # this program never opens a subject file any other way.
    with resolved.open("rb") as handle:
        handle.read(1)
    return resolved


def read_metadata(
    paths: Sequence[Path],
    *,
    executable: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Read every tag from each file, with group names, as ExifTool reports it."""
    if not paths:
        return []

    command = build_command(executable or find_exiftool())
    resolved = [check_readable(path) for path in paths]

    with tempfile.TemporaryDirectory(prefix="camera-count-") as work:
        argfile = Path(work) / "exiftool.args"
        lines = [*READ_ARGUMENTS, "-charset", "filename=utf8"]
        lines.extend(str(item) for item in resolved)
        argfile.write_text("\n".join(lines) + "\n", encoding="utf-8")

        output = _run([*command, "-@", str(argfile)], timeout=timeout)

    try:
        parsed = json.loads(output or "[]")
    except json.JSONDecodeError as exc:
        raise MetadataError(f"ExifTool returned output that is not JSON: {exc}") from exc

    if not isinstance(parsed, list):
        raise MetadataError("ExifTool returned an unexpected JSON shape")

    return [item for item in parsed if isinstance(item, dict)]
