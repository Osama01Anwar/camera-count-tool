"""The camera-count command line interface."""

from __future__ import annotations

__all__ = ["app", "run"]


def __getattr__(name: str) -> object:
    """Import the Typer app lazily so ``import camera_count.cli`` stays cheap."""
    if name in __all__:
        from camera_count.cli.main import app, run  # noqa: PLC0415

        return {"app": app, "run": run}[name]
    raise AttributeError(name)
