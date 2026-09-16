"""Desktop application entry point."""

from __future__ import annotations

import sys

from camera_count import __version__


def run() -> int:
    """Start the desktop app. Returns the process exit code."""
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    from camera_count.gui.window import build_window  # noqa: PLC0415
    from camera_count.registry import load_default_registry  # noqa: PLC0415

    # Loading the registry first means the reading guard has its resolver before
    # any window can ask for a count.
    load_default_registry()

    application = QApplication(sys.argv)
    application.setApplicationName("Camera Count Tool")
    application.setApplicationVersion(__version__)
    application.setOrganizationName("Camera Count Tool")

    window = build_window()
    window.show()
    return int(application.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
