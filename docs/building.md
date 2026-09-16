# Building

## Requirements

- Windows 10 or 11, x64
- Python 3.12
- [uv](https://docs.astral.sh/uv/) (or pip, if you prefer)
- Inno Setup 6, only to build the installer

## From a checkout

```powershell
git clone https://github.com/Osama01Anwar/camera-count-tool
cd camera-count-tool
uv venv --python 3.12
uv pip install -e ".[dev]"
```

Then:

```powershell
uv run ruff check . ; uv run ruff format --check .
uv run mypy
uv run pytest
uv run camera-count --version
```

## ExifTool

Packaged releases bundle ExifTool so users need nothing installed. For a build,
fetch it first:

```powershell
uv run python scripts/fetch_exiftool.py
```

The archive is checked against the SHA-256 published on exiftool.org before it
is unpacked. If that download is blocked on your network, a development machine
with Perl can use the source distribution instead:

```powershell
uv run python scripts/fetch_exiftool.py --mode source
```

That form is verified by running the result and checking it reports the pinned
version. It is for development only - it needs Perl, which a user will not have.
Git for Windows ships one at `C:\Program Files\Git\usr\bin\perl.exe`, which the
tool will find.

## The distribution

```powershell
uv run python scripts/generate_third_party_licenses.py
uv run python packaging/build.py
uv run python packaging/verify_release.py
```

This produces:

```
packaging/output/
  CameraCountTool/                                  one folder, two executables
  CameraCountTool-<version>-windows-x64-portable.zip
  SHA256SUMS.txt
```

`verify_release.py` is the gate. It checks that no mock or test code is in the
distribution, that the registry and its schema are present, that ExifTool is
bundled, and - the important one - that the built `camera-count.exe` runs and
loads the registry **with every Python directory stripped from PATH**. A
distribution that only works on a machine that already has Python is not a
distribution.

For a local build on a machine that could not fetch ExifTool, add
`--allow-missing-exiftool`. Never pass that in CI.

## The installer

```powershell
uv run python packaging/build_installer.py
```

Needs `iscc.exe` from [Inno Setup](https://jrsoftware.org/isdl.php). The
installer copies files and creates shortcuts. It installs no driver, no service
and no startup entry, and touches nothing outside its own directory. Adding
`camera-count` to PATH is an opt-in checkbox.

## Why one folder rather than one file

Two reasons. PySide6 is LGPL, and keeping the Qt libraries as separate
replaceable files next to the application is what that licence expects, rather
than welding them into a single executable. And a one-file build unpacks itself
to a temporary directory on every run, which is slower and makes the bundled
ExifTool harder to find.

## Regenerating documentation

```powershell
uv run python scripts/generate_support_docs.py
```

`docs/manufacturer-support.md` is generated from the registry, and CI fails if
the committed copy has drifted from the data.

## Signing

Releases are unsigned. There is no certificate, so SmartScreen warns on first
run and the SHA256SUMS file is how a user checks what they downloaded. If the
project ever gets a certificate, signing belongs in the release workflow after
`verify_release.py`, never before it.
