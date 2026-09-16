"""GUI tests run without a desktop session."""

from __future__ import annotations

import os

# Must be set before Qt is imported anywhere in the process.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
