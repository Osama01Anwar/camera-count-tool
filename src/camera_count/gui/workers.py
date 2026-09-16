"""Background work, so the window never freezes while a camera is read.

Talking to a camera or running ExifTool takes long enough to be noticeable, and
a frozen window looks like a crash. Each job runs on its own thread and reports
back through signals.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal


class Task(QThread):
    """Runs one callable off the UI thread and reports the outcome."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, work: Callable[[], Any], parent: Any = None) -> None:
        super().__init__(parent)
        self._work = work

    def run(self) -> None:  # pragma: no cover - exercised through the GUI
        try:
            outcome = self._work()
        except Exception as exc:  # noqa: BLE001 - a failed job must not kill the app
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(outcome)


def inspect_task(parent: Any = None) -> Task:
    """Read the connected camera."""
    from camera_count.inspection import inspect_camera  # noqa: PLC0415

    return Task(inspect_camera, parent)


def detect_task(parent: Any = None) -> Task:
    """Check what is connected, for the hot-plug watcher."""
    from camera_count.usb.enumerate import detect  # noqa: PLC0415

    return Task(detect, parent)


def analyze_task(paths: Sequence[Path], parent: Any = None) -> Task:
    """Analyse one or more image files."""
    from camera_count.metadata import analyze_files  # noqa: PLC0415

    return Task(lambda: analyze_files(list(paths)), parent)
