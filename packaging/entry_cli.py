"""Console entry point for the frozen build."""

from __future__ import annotations

import multiprocessing

from camera_count.cli.main import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
