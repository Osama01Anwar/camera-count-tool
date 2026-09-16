"""Mock devices for development and tests. Never packaged into a release.

Everything produced here is labelled MOCK CAMERA - TEST ONLY. The CLI only
exposes ``--dev-mock`` when this package is importable *and* the
CAMERA_COUNT_DEV environment variable is set, and packaging/verify_release.py
fails the build if any of it appears inside a distribution.
"""

from __future__ import annotations

from typing import Final

MOCK_LABEL: Final = "MOCK CAMERA - TEST ONLY"

__all__ = ["MOCK_LABEL"]
