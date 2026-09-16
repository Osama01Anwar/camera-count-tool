"""Compile the Windows installer with Inno Setup.

Expects packaging/build.py to have produced the distribution folder first, and
expects the Inno Setup compiler (iscc.exe) to be available. GitHub's
windows-latest runner ships it; a local machine may need it from
https://jrsoftware.org/isdl.php.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGING: Final = REPO_ROOT / "packaging"
OUTPUT: Final = PACKAGING / "output"
DISTRIBUTION: Final = OUTPUT / "CameraCountTool"
SCRIPT: Final = PACKAGING / "installer.iss"

CANDIDATES: Final[tuple[str, ...]] = (
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
)


def find_compiler() -> Path | None:
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return Path(found)
    for candidate in CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def version() -> str:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from camera_count import __version__  # noqa: PLC0415

    return __version__


def append_checksum(installer: Path) -> None:
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    sums = OUTPUT / "SHA256SUMS.txt"
    line = f"{digest}  {installer.name}\n"
    existing = sums.read_text(encoding="utf-8") if sums.is_file() else ""
    if installer.name not in existing:
        sums.write_text(existing + line, encoding="utf-8")
    print(f"{digest}  {installer.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--optional",
        action="store_true",
        help="Report a missing compiler instead of failing.",
    )
    args = parser.parse_args()

    if not DISTRIBUTION.is_dir():
        print(f"no distribution at {DISTRIBUTION}; run packaging/build.py first", file=sys.stderr)
        return 1

    compiler = find_compiler()
    if compiler is None:
        message = (
            "Inno Setup (iscc.exe) was not found. Install it from "
            "https://jrsoftware.org/isdl.php to build the installer."
        )
        if args.optional:
            print(message)
            return 0
        print(message, file=sys.stderr)
        return 1

    app_version = version()
    command = [
        str(compiler),
        f"/DAppVersion={app_version}",
        f"/DSourceFolder={DISTRIBUTION}",
        f"/DOutputFolder={OUTPUT}",
        str(SCRIPT),
    ]
    print("running:", " ".join(command))
    completed = subprocess.run(  # noqa: S603 - explicit argument list
        command, cwd=PACKAGING, check=False, shell=False, env=dict(os.environ)
    )
    if completed.returncode != 0:
        return completed.returncode

    installer = OUTPUT / f"CameraCountTool-{app_version}-windows-x64-setup.exe"
    if not installer.is_file():
        print(f"the compiler reported success but {installer} is missing", file=sys.stderr)
        return 1

    print(f"built {installer}")
    append_checksum(installer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
