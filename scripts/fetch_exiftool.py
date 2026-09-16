"""Download the pinned ExifTool build and verify it before use.

This is a build-time script, not shipped code: it is the one place in the
repository allowed to touch the network, and nothing under ``src/`` may import
it. The archive is checked against a SHA-256 recorded here from exiftool.org's
published checksums before a single byte of it is extracted.

Updating the pin means changing both constants together, after checking the new
value at https://exiftool.org/checksums.txt.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Final

EXIFTOOL_VERSION: Final = "13.59"

#: SHA2-256(exiftool-13.59_64.zip) from https://exiftool.org/checksums.txt
EXIFTOOL_SHA256: Final = "44b512b25af500724ba579d0a53c8fc5851628b692dd5e5d94ae4a15c2cba9ec"

ARCHIVE_NAME: Final = f"exiftool-{EXIFTOOL_VERSION}_64.zip"

#: exiftool.org links its Windows builds to SourceForge, so that is the primary
#: source. The checksum above is what makes the mirror choice irrelevant: a
#: wrong or tampered file fails verification and is never extracted.
DOWNLOAD_URLS: Final[tuple[str, ...]] = (
    f"https://sourceforge.net/projects/exiftool/files/{ARCHIVE_NAME}/download",
    f"https://exiftool.org/{ARCHIVE_NAME}",
    f"https://exiftool.org/oldVersions/{ARCHIVE_NAME}",
)

REPO_ROOT: Final = Path(__file__).resolve().parents[1]
VENDOR_DIR: Final = REPO_ROOT / "packaging" / "vendor" / "exiftool"

DOWNLOAD_TIMEOUT_SECONDS: Final = 300
MAX_ARCHIVE_BYTES: Final = 64 * 1024 * 1024


def download(url: str) -> bytes:
    print(f"downloading {url}")
    request = urllib.request.Request(  # noqa: S310 - fixed https URL, verified below
        url, headers={"User-Agent": "camera-count-tool build script"}
    )
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:  # noqa: S310
        payload: bytes = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise SystemExit(f"archive is larger than {MAX_ARCHIVE_BYTES} bytes; refusing")
    return payload


def verify(payload: bytes) -> None:
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXIFTOOL_SHA256:
        raise SystemExit(
            "checksum mismatch - refusing to use this download.\n"
            f"  expected {EXIFTOOL_SHA256}\n  got      {digest}"
        )
    print(f"sha256 verified: {digest}")


def extract(payload: bytes, destination: Path) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    archive_path = destination / ARCHIVE_NAME
    archive_path.write_bytes(payload)

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.namelist():
            target = (destination / member).resolve()
            if not str(target).startswith(str(destination.resolve())):
                raise SystemExit(f"archive contains a path outside the target: {member}")
        archive.extractall(destination)  # noqa: S202 - every member checked above
    archive_path.unlink()

    # The distribution ships the binary as "exiftool(-k).exe", which pauses for
    # a keypress when double-clicked. Renaming it is the documented way to get
    # the plain command-line behaviour.
    inner = next((p for p in destination.iterdir() if p.is_dir()), None)
    root = inner or destination
    if inner is not None:
        for item in list(inner.iterdir()):
            shutil.move(str(item), str(destination / item.name))
        inner.rmdir()
        root = destination

    for candidate in ("exiftool(-k).exe", "exiftool.exe"):
        source = root / candidate
        if source.is_file():
            final = root / "exiftool.exe"
            if source != final:
                source.rename(final)
            return final

    raise SystemExit(f"no exiftool executable found in {root}")


def fetch_source() -> int:
    """Development fallback: the Perl distribution from the official GitHub repo.

    This is for working on the project on a machine that has Perl. It is **not**
    what ships: a release bundles the self-contained Windows executable, so that
    users need neither Perl nor Python. The archive GitHub builds from a tag is
    not covered by the published checksum, so it is verified by running the
    result and checking it reports the pinned version.
    """
    import subprocess  # noqa: PLC0415
    import tarfile  # noqa: PLC0415

    url = f"https://codeload.github.com/exiftool/exiftool/tar.gz/refs/tags/{EXIFTOOL_VERSION}"
    payload = download(url)

    destination = REPO_ROOT / "packaging" / "vendor"
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / f"exiftool-{EXIFTOOL_VERSION}-source.tar.gz"
    archive_path.write_bytes(payload)

    with tarfile.open(archive_path) as archive:
        archive.extractall(destination, filter="data")
    archive_path.unlink()

    script = destination / f"exiftool-{EXIFTOOL_VERSION}" / "exiftool"
    if not script.is_file():
        raise SystemExit(f"the archive did not contain {script}")

    perl = shutil.which("perl") or r"C:\Program Files\Git\usr\bin\perl.exe"
    if not Path(perl).is_file():
        print(f"extracted to {script}, but no Perl interpreter was found to verify it")
        return 0

    completed = subprocess.run(  # noqa: S603 - explicit argument list
        [perl, str(script), "-ver"], capture_output=True, check=False, shell=False
    )
    reported = completed.stdout.decode("utf-8", errors="replace").strip()
    if reported != EXIFTOOL_VERSION:
        raise SystemExit(
            f"the extracted ExifTool reports {reported!r}, expected {EXIFTOOL_VERSION!r}"
        )
    print(f"ExifTool {reported} (Perl distribution) ready at {script}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Download again even if already present."
    )
    parser.add_argument(
        "--mode",
        choices=("exe", "source"),
        default="exe",
        help=(
            "exe: the self-contained Windows build that ships in releases. "
            "source: the Perl distribution, for development machines with Perl."
        ),
    )
    args = parser.parse_args()

    if args.mode == "source":
        return fetch_source()

    executable = VENDOR_DIR / "exiftool.exe"
    if executable.is_file() and not args.force:
        print(f"already present: {executable}")
        return 0

    last_error: Exception | None = None
    for url in DOWNLOAD_URLS:
        try:
            payload = download(url)
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            print(f"  failed: {exc}")
            last_error = exc
            continue
        verify(payload)
        final = extract(payload, VENDOR_DIR)
        print(f"ExifTool {EXIFTOOL_VERSION} ready at {final}")
        return 0

    print(f"could not download ExifTool: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
