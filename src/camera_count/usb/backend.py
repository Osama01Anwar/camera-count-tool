"""The enumeration backend interface and its result type.

A backend that cannot run (missing library, wrong platform, no permission)
reports that fact instead of raising, so ``detect`` can tell the user exactly
why a camera is not showing up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from camera_count.usb.models import UsbDeviceInfo


@dataclass(frozen=True, slots=True)
class EnumerationResult:
    """What one backend found, and what stopped it if it found nothing."""

    backend: str
    available: bool
    devices: tuple[UsbDeviceInfo, ...] = ()
    unavailable_reason: str | None = None
    warnings: tuple[str, ...] = field(default=())

    @property
    def device_count(self) -> int:
        return len(self.devices)


@runtime_checkable
class EnumerationBackend(Protocol):
    """Something that can list USB devices on this machine."""

    @property
    def name(self) -> str: ...

    def is_available(self) -> tuple[bool, str | None]:
        """Return (available, reason-if-not)."""
        ...

    def enumerate(self) -> EnumerationResult: ...
