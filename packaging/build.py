"""Build the Windows distribution.

Produces ``packaging/output/CameraCountTool/`` containing both executables and
everything they need, so a user needs neither Python nor ExifTool installed.
Also writes a portable zip and a SHA256SUMS.txt beside it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGING: Final = REPO_ROOT / "packaging"
OUTPUT: Final = PACKAGING / "output"
BUILD_WORK: Final = PACKAGING / "build"
SPEC: Final = PACKAGING / "camera_count.spec"
VENDOR_EXIFTOOL: Final = PACKAGING / "vendor" / "exiftool" / "exiftool.exe"


def version() -> str:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from camera_count import __version__  # noqa: PLC0415

    return __version__


def run_pyinstaller() -> Path:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    environment = dict(os.environ, CAMERA_COUNT_REPO=str(REPO_ROOT))
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(OUTPUT),
        "--workpath",
        str(BUILD_WORK),
        str(SPEC),
    ]
    print("running:", " ".join(command))
    completed = subprocess.run(  # noqa: S603 - explicit argument list
        command, cwd=REPO_ROOT, env=environment, check=False, shell=False
    )
    if completed.returncode != 0:
        raise SystemExit(f"PyInstaller failed with exit code {completed.returncode}")

    folder = OUTPUT / "CameraCountTool"
    if not folder.is_dir():
        raise SystemExit(f"expected a distribution at {folder}")
    return folder


def make_zip(folder: Path, name: str) -> Path:
    archive = OUTPUT / name
    print(f"writing {archive}")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for item in sorted(folder.rglob("*")):
            if item.is_file():
                bundle.write(item, item.relative_to(folder.parent).as_posix())
    return archive


def write_checksums(paths: list[Path]) -> Path:
    lines = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    target = OUTPUT / "SHA256SUMS.txt"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-zip", action="store_true", help="Build the folder but no archive.")
    args = parser.parse_args()

    if not VENDOR_EXIFTOOL.is_file():
        print(
            "WARNING: ExifTool has not been vendored, so image mode will not work "
            "in this build. Run scripts/fetch_exiftool.py first.",
            file=sys.stderr,
        )

    folder = run_pyinstaller()
    print(f"built {folder}")

    if args.skip_zip:
        return 0

    archive = make_zip(folder, f"CameraCountTool-{version()}-windows-x64-portable.zip")
    write_checksums([archive])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
