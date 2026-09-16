# PyInstaller spec: one folder, two executables.
#
# The desktop app and the command line share a single set of collected files,
# so the distribution is not shipped twice. The desktop analysis is a superset
# of the console one, so its binaries and data are what get collected.
#
# Mock devices live under tests/ and are never importable from here; the
# excludes below make that structural rather than incidental, and
# packaging/verify_release.py checks the built folder afterwards.

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("CAMERA_COUNT_REPO", ".")).resolve()
PACKAGING = REPO_ROOT / "packaging"
VENDOR_EXIFTOOL = PACKAGING / "vendor" / "exiftool"

datas = [
    (str(REPO_ROOT / "src" / "camera_count" / "registry" / "camera_database"),
     "camera_count/registry/camera_database"),
    (str(REPO_ROOT / "src" / "camera_count" / "registry" / "camera_model.schema.json"),
     "camera_count/registry"),
    (str(REPO_ROOT / "src" / "camera_count" / "db" / "migrations"),
     "camera_count/db/migrations"),
    (str(REPO_ROOT / "LICENSE"), "."),
    (str(REPO_ROOT / "NOTICE"), "."),
]

for extra in ("THIRD_PARTY_LICENSES.md", "README.md"):
    candidate = REPO_ROOT / extra
    if candidate.is_file():
        datas.append((str(candidate), "."))

# ExifTool, when it has been vendored. The build script warns if it is absent;
# verify_release.py refuses to bless a release without it.
if VENDOR_EXIFTOOL.is_dir():
    datas.append((str(VENDOR_EXIFTOOL), "exiftool"))

EXCLUDES = [
    "tests",
    "devmock",
    "pytest",
    "hypothesis",
    "mypy",
    "ruff",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "tkinter",
]

HIDDEN = [
    "camera_count.cli.main",
    "camera_count.gui.main",
    "comtypes",
    "comtypes.client",
]

gui_analysis = Analysis(
    [str(PACKAGING / "entry_gui.py")],
    pathex=[str(REPO_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=HIDDEN,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

cli_analysis = Analysis(
    [str(PACKAGING / "entry_cli.py")],
    pathex=[str(REPO_ROOT / "src")],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

gui_pyz = PYZ(gui_analysis.pure)
cli_pyz = PYZ(cli_analysis.pure)

gui_exe = EXE(
    gui_pyz,
    gui_analysis.scripts,
    [],
    exclude_binaries=True,
    name="CameraCountTool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

cli_exe = EXE(
    cli_pyz,
    cli_analysis.scripts,
    [],
    exclude_binaries=True,
    name="camera-count",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

collected = COLLECT(
    gui_exe,
    cli_exe,
    gui_analysis.binaries,
    gui_analysis.datas,
    strip=False,
    upx=False,
    name="CameraCountTool",
)
