"""MOCK CAMERA - TEST ONLY.

A transport that answers from a script instead of from hardware, plus helpers
that build well-formed PTP payloads. Nothing here is packaged into a release;
packaging/verify_release.py fails the build if it ever is.

Counts used in these helpers are deliberately odd-looking so that a number from
a mock can never be mistaken for a reading from a real camera.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field

from camera_count.ptp.constants import ContainerType, ResponseCode
from camera_count.ptp.transport import TransactionResult
from tests.devmock import MOCK_LABEL


def ptp_string(text: str) -> bytes:
    """Encode a PTP string: one byte of character count, then UTF-16LE."""
    if not text:
        return b"\x00"
    encoded = (text + "\x00").encode("utf-16-le")
    return bytes([len(text) + 1]) + encoded


def ptp_uint16_array(values: Sequence[int]) -> bytes:
    return struct.pack("<I", len(values)) + b"".join(struct.pack("<H", value) for value in values)


def build_device_info(
    *,
    standard_version: int = 100,
    vendor_extension_id: int = 0,
    vendor_extension_version: int = 0,
    vendor_extension_desc: str = "",
    functional_mode: int = 0,
    operations_supported: Sequence[int] = (0x1001, 0x1002, 0x1003),
    events_supported: Sequence[int] = (),
    device_properties_supported: Sequence[int] = (),
    capture_formats: Sequence[int] = (),
    image_formats: Sequence[int] = (),
    manufacturer: str = "MOCK CAMERA - TEST ONLY",
    model: str = "MOCK BODY - TEST ONLY",
    device_version: str = "0.0-mock",
    serial_number: str = "MOCKSERIAL000",
) -> bytes:
    """Build a DeviceInfo payload in the standard field order."""
    return b"".join(
        [
            struct.pack("<H", standard_version),
            struct.pack("<I", vendor_extension_id),
            struct.pack("<H", vendor_extension_version),
            ptp_string(vendor_extension_desc),
            struct.pack("<H", functional_mode),
            ptp_uint16_array(operations_supported),
            ptp_uint16_array(events_supported),
            ptp_uint16_array(device_properties_supported),
            ptp_uint16_array(capture_formats),
            ptp_uint16_array(image_formats),
            ptp_string(manufacturer),
            ptp_string(model),
            ptp_string(device_version),
            ptp_string(serial_number),
        ]
    )


def build_property_description(
    property_code: int, data_type: int, *, writable: bool = False
) -> bytes:
    """Build the header of a DevicePropDesc dataset."""
    return (
        struct.pack("<H", property_code)
        + struct.pack("<H", data_type)
        + bytes([0x01 if writable else 0x00])
    )


def build_container(
    container_type: ContainerType, code: int, transaction_id: int, payload: bytes = b""
) -> bytes:
    return (
        struct.pack("<IHHI", 12 + len(payload), container_type.value, code, transaction_id)
        + payload
    )


@dataclass
class MockTransport:
    """MOCK CAMERA - TEST ONLY. Answers operations from a script."""

    responses: dict[int, TransactionResult] = field(default_factory=dict)
    label: str = MOCK_LABEL
    sent: list[tuple[int, tuple[int, ...]]] = field(default_factory=list)
    opened: bool = False
    closed: bool = False
    fail_open: str | None = None

    @property
    def name(self) -> str:
        return "mock"

    def open(self) -> None:
        if self.fail_open:
            from camera_count.core.errors import DeviceAccessError

            raise DeviceAccessError(self.fail_open)
        self.opened = True

    def close(self) -> None:
        self.closed = True
        self.opened = False

    def transaction(
        self,
        *,
        code: int,
        parameters: Sequence[int] = (),
        expect_data: bool = False,
        timeout_ms: int | None = None,
    ) -> TransactionResult:
        self.sent.append((code, tuple(parameters)))
        return self.responses.get(code, TransactionResult(response_code=ResponseCode.OK.value))

    # -- assertions used by tests --------------------------------------------

    @property
    def sent_codes(self) -> tuple[int, ...]:
        return tuple(code for code, _ in self.sent)

    def was_sent(self, code: int) -> bool:
        return code in self.sent_codes
