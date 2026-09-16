"""Camera Count Tool.

Reports a shutter count only when it can obtain that count from an
authoritative source. When an exact count cannot be obtained, it reports the
count as unavailable and says why. It never invents a number.

This package performs no network access of any kind.
"""

from __future__ import annotations

from typing import Final

__version__: Final = "0.1.0"
__all__ = ["__version__"]
