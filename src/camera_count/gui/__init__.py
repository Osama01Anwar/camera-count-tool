"""The desktop application."""

from __future__ import annotations

__all__ = ["run"]


def __getattr__(name: str) -> object:
    """Import Qt lazily, so importing this package does not start a GUI stack."""
    if name == "run":
        from camera_count.gui.main import run  # noqa: PLC0415

        return run
    raise AttributeError(name)
