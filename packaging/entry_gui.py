"""Desktop entry point for the frozen build."""

from __future__ import annotations

import multiprocessing
import sys

from camera_count.gui.main import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(run())
