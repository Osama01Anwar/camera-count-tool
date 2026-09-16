"""The interface adapters talk to.

Windows reaches a camera through Windows Portable Devices; a machine with a
WinUSB driver can reach one through libusb and raw PTP instead. Adapters should
not care which, so both expose the same three read-only capabilities:
identity, a device property read, and a vendor operation that returns data.

There is no write capability here, and none anywhere below it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from camera_count.core.models import CameraIdentity
from camera_count.diagnostics.log import TransactionLog
from camera_count.ptp.transport import TransactionResult


@runtime_checkable
class CameraLink(Protocol):
    """An open, read-only connection to one camera."""

    @property
    def name(self) -> str:
        """Short name of the underlying transport, for logs and reports."""
        ...

    @property
    def log(self) -> TransactionLog:
        """The transaction log every reading must be traceable to."""
        ...

    @property
    def allowed_opcodes(self) -> frozenset[int]:
        """Vendor operations this link may send. Everything else is refused."""
        ...

    def identity(self) -> CameraIdentity:
        """What the camera says it is. Unknown fields come back as None."""
        ...

    def read_device_property(self, code: int) -> tuple[int, str] | None:
        """Read one device property as an unsigned integer.

        Returns ``(value, transaction_reference)``, or ``None`` when the camera
        does not provide that property.
        """
        ...

    def execute_read_operation(
        self, code: int, parameters: tuple[int, ...] = (), *, expect_data: bool = False
    ) -> TransactionResult:
        """Send an allow-listed read operation and return what came back."""
        ...
