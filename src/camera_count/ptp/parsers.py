"""Bounded readers for untrusted device payloads.

Every read checks that the bytes it needs are actually there before slicing, and
every count read off the wire is checked against a cap before it is used to
size anything. A hostile or broken camera gets a :class:`ParseError`, never an
allocation it chose.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from camera_count.core.errors import ParseError
from camera_count.ptp.constants import (
    MAX_ARRAY_ELEMENTS,
    MAX_STRING_CHARS,
    SCALAR_WIDTHS,
    SIGNED_TYPES,
    DataType,
)

_FORMATS: Final[dict[int, str]] = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}
_SIGNED_FORMATS: Final[dict[int, str]] = {1: "<b", 2: "<h", 4: "<i", 8: "<q"}


class ByteReader:
    """A cursor over untrusted bytes that refuses to read past the end."""

    __slots__ = ("_data", "_offset", "_origin")

    def __init__(self, data: bytes, *, origin: str = "device") -> None:
        self._data = data
        self._offset = 0
        self._origin = origin

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def remaining(self) -> int:
        return len(self._data) - self._offset

    def take(self, count: int) -> bytes:
        if count < 0:
            raise ParseError(f"{self._origin}: negative read of {count} bytes")
        if count > self.remaining:
            raise ParseError(
                f"{self._origin}: needs {count} bytes at offset {self._offset} "
                f"but only {self.remaining} remain"
            )
        chunk = self._data[self._offset : self._offset + count]
        self._offset += count
        return chunk

    # -- scalars --------------------------------------------------------------

    def uint(self, width: int) -> int:
        fmt = _FORMATS.get(width)
        if fmt is None:
            return int.from_bytes(self.take(width), "little", signed=False)
        return int(struct.unpack(fmt, self.take(width))[0])

    def sint(self, width: int) -> int:
        fmt = _SIGNED_FORMATS.get(width)
        if fmt is None:
            return int.from_bytes(self.take(width), "little", signed=True)
        return int(struct.unpack(fmt, self.take(width))[0])

    def u8(self) -> int:
        return self.uint(1)

    def u16(self) -> int:
        return self.uint(2)

    def u32(self) -> int:
        return self.uint(4)

    def u64(self) -> int:
        return self.uint(8)

    # -- composites -----------------------------------------------------------

    def string(self) -> str:
        """Read a PTP string: one byte of character count, then UTF-16LE."""
        char_count = self.u8()
        if char_count == 0:
            return ""
        if char_count > MAX_STRING_CHARS:
            raise ParseError(
                f"{self._origin}: string claims {char_count} characters, over the "
                f"{MAX_STRING_CHARS} limit"
            )
        raw = self.take(char_count * 2)
        try:
            text = raw.decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise ParseError(f"{self._origin}: string is not valid UTF-16: {exc}") from exc
        return text.rstrip("\x00")

    def array(self, element: Callable[[], int]) -> tuple[int, ...]:
        """Read a uint32-counted array, with the count capped before allocation."""
        count = self.u32()
        if count > MAX_ARRAY_ELEMENTS:
            raise ParseError(
                f"{self._origin}: array claims {count} elements, over the "
                f"{MAX_ARRAY_ELEMENTS} limit"
            )
        return tuple(element() for _ in range(count))

    def uint16_array(self) -> tuple[int, ...]:
        return self.array(self.u16)

    def uint32_array(self) -> tuple[int, ...]:
        return self.array(self.u32)


def read_typed_value(reader: ByteReader, data_type: DataType) -> int | str | tuple[int, ...]:
    """Read one value of ``data_type``.

    Only the types the standard defines are accepted. An unknown type code is a
    parse failure, never a best guess at the width.
    """
    if data_type is DataType.STR:
        return reader.string()

    width = SCALAR_WIDTHS.get(data_type)
    if width is not None:
        return reader.sint(width) if data_type in SIGNED_TYPES else reader.uint(width)

    if data_type.value & 0x4000:
        element_type = DataType(data_type.value & 0x00FF)
        element_width = SCALAR_WIDTHS.get(element_type)
        if element_width is None:
            raise ParseError(f"unsupported array element type 0x{element_type.value:04X}")
        signed = element_type in SIGNED_TYPES
        return reader.array(
            lambda: reader.sint(element_width) if signed else reader.uint(element_width)
        )

    raise ParseError(f"unsupported data type 0x{data_type.value:04X}")


def coerce_counter(value: int | str | tuple[int, ...]) -> int:
    """Turn a property value into a counter integer, or refuse.

    A counter must arrive as a single unsigned integer. A string, an array, or
    anything negative is refused outright: this program does not convert,
    reinterpret, or pick an element out of a structure to find a number.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParseError(f"a counter must be a single integer, got {type(value).__name__}")
    if value < 0:
        raise ParseError(f"a counter must not be negative, got {value}")
    return value


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    """The DeviceInfo dataset, exactly as the device reported it."""

    standard_version: int = 0
    vendor_extension_id: int = 0
    vendor_extension_version: int = 0
    vendor_extension_desc: str = ""
    functional_mode: int = 0
    operations_supported: tuple[int, ...] = ()
    events_supported: tuple[int, ...] = ()
    device_properties_supported: tuple[int, ...] = ()
    capture_formats: tuple[int, ...] = ()
    image_formats: tuple[int, ...] = ()
    manufacturer: str = ""
    model: str = ""
    device_version: str = ""
    serial_number: str = ""

    def supports_operation(self, code: int) -> bool:
        return code in self.operations_supported

    def supports_property(self, code: int) -> bool:
        return code in self.device_properties_supported


def parse_device_info(payload: bytes) -> DeviceInfo:
    """Parse a DeviceInfo data payload.

    Field order is from the PTP standard's DeviceInfo dataset. Truncated
    payloads raise rather than yielding partly-filled identity fields.
    """
    reader = ByteReader(payload, origin="DeviceInfo")
    return DeviceInfo(
        standard_version=reader.u16(),
        vendor_extension_id=reader.u32(),
        vendor_extension_version=reader.u16(),
        vendor_extension_desc=reader.string(),
        functional_mode=reader.u16(),
        operations_supported=reader.uint16_array(),
        events_supported=reader.uint16_array(),
        device_properties_supported=reader.uint16_array(),
        capture_formats=reader.uint16_array(),
        image_formats=reader.uint16_array(),
        manufacturer=reader.string(),
        model=reader.string(),
        device_version=reader.string(),
        serial_number=reader.string(),
    )


@dataclass(frozen=True, slots=True)
class DevicePropertyDescription:
    """The header of a DevicePropDesc dataset.

    The form-flag section beyond the default value is not parsed: nothing in
    this program needs it, and every byte parsed is a byte that can go wrong.
    """

    property_code: int
    data_type: DataType
    writable: bool
    raw: bytes = field(repr=False, default=b"")


def parse_device_property_description(payload: bytes) -> DevicePropertyDescription:
    """Parse enough of a DevicePropDesc to know how to read the value."""
    reader = ByteReader(payload, origin="DevicePropDesc")
    property_code = reader.u16()
    raw_type = reader.u16()
    try:
        data_type = DataType(raw_type)
    except ValueError as exc:
        raise ParseError(f"DevicePropDesc: unknown data type 0x{raw_type:04X}") from exc
    get_set = reader.u8()
    return DevicePropertyDescription(
        property_code=property_code,
        data_type=data_type,
        writable=get_set == 0x01,
        raw=payload,
    )
