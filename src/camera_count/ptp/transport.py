"""The transport interface.

A transport can send a command container and read back data and a response.
That is the whole interface - there is deliberately no way to attach an
outbound data phase, which is what makes "we never write to the camera" a
property of the type system rather than a promise in the documentation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TransactionResult:
    """What came back from one operation."""

    response_code: int
    response_parameters: tuple[int, ...] = ()
    data: bytes = field(repr=False, default=b"")


@runtime_checkable
class Transport(Protocol):
    """A read-only PTP transport."""

    @property
    def name(self) -> str:
        """Short transport name for logs and reports."""
        ...

    def open(self) -> None:
        """Claim the device. Raises DeviceAccessError if it cannot be claimed."""
        ...

    def close(self) -> None:
        """Release the device. Safe to call more than once."""
        ...

    def transaction(
        self,
        *,
        code: int,
        parameters: Sequence[int] = (),
        expect_data: bool = False,
        timeout_ms: int | None = None,
    ) -> TransactionResult:
        """Send a command container and read the response.

        Implementations must never send a data phase: there is no parameter
        here through which caller data could reach the device.
        """
        ...
