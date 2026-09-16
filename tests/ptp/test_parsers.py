"""Bounded parsing of untrusted payloads."""

from __future__ import annotations

import struct

import pytest

from camera_count.core.errors import ParseError
from camera_count.ptp.constants import MAX_ARRAY_ELEMENTS, MAX_STRING_CHARS, DataType
from camera_count.ptp.parsers import (
    ByteReader,
    coerce_counter,
    parse_device_info,
    parse_device_property_description,
    read_typed_value,
)
from tests.devmock.transport import build_device_info, build_property_description, ptp_string


def test_reader_refuses_to_read_past_the_end() -> None:
    reader = ByteReader(b"\x01\x02")

    assert reader.u16() == 0x0201
    with pytest.raises(ParseError, match="only 0 remain"):
        reader.u8()


def test_reader_refuses_a_negative_read() -> None:
    with pytest.raises(ParseError, match="negative read"):
        ByteReader(b"\x00").take(-1)


def test_string_round_trip() -> None:
    reader = ByteReader(ptp_string("NIKON Z 6_2"))

    assert reader.string() == "NIKON Z 6_2"


def test_empty_string_is_one_zero_byte() -> None:
    assert ByteReader(b"\x00").string() == ""


def test_string_longer_than_the_cap_is_refused() -> None:
    payload = bytes([MAX_STRING_CHARS]) + b"A\x00" * MAX_STRING_CHARS
    assert ByteReader(payload).string()

    truncated = bytes([200]) + b"A\x00" * 4
    with pytest.raises(ParseError, match="needs 400 bytes"):
        ByteReader(truncated).string()


def test_array_count_is_capped_before_allocation() -> None:
    payload = struct.pack("<I", MAX_ARRAY_ELEMENTS + 1)

    with pytest.raises(ParseError, match="over the"):
        ByteReader(payload).uint32_array()


def test_array_shorter_than_its_count_is_refused() -> None:
    payload = struct.pack("<I", 10) + b"\x01\x00"

    with pytest.raises(ParseError):
        ByteReader(payload).uint16_array()


def test_device_info_is_parsed_in_standard_field_order() -> None:
    payload = build_device_info(
        standard_version=100,
        operations_supported=(0x1001, 0x1014, 0x1015),
        device_properties_supported=(0xD1A3,),
        manufacturer="MOCK CAMERA - TEST ONLY",
        model="MOCK BODY - TEST ONLY",
        device_version="1.0-mock",
        serial_number="MOCK123",
    )

    info = parse_device_info(payload)

    assert info.standard_version == 100
    assert info.manufacturer == "MOCK CAMERA - TEST ONLY"
    assert info.model == "MOCK BODY - TEST ONLY"
    assert info.device_version == "1.0-mock"
    assert info.serial_number == "MOCK123"
    assert info.supports_operation(0x1015)
    assert info.supports_property(0xD1A3)
    assert not info.supports_property(0x0001)


def test_truncated_device_info_raises_rather_than_half_filling_identity() -> None:
    payload = build_device_info()[:20]

    with pytest.raises(ParseError):
        parse_device_info(payload)


def test_property_description_reports_type_and_writability() -> None:
    description = parse_device_property_description(
        build_property_description(0xD1A3, DataType.UINT32.value, writable=False)
    )

    assert description.property_code == 0xD1A3
    assert description.data_type is DataType.UINT32
    assert not description.writable


def test_unknown_property_data_type_is_refused() -> None:
    with pytest.raises(ParseError, match="unknown data type"):
        parse_device_property_description(build_property_description(0xD1A3, 0x1234))


@pytest.mark.parametrize(
    ("data_type", "payload", "expected"),
    [
        (DataType.UINT8, b"\x2a", 42),
        (DataType.UINT16, b"\x2a\x00", 42),
        (DataType.UINT32, b"\x2a\x00\x00\x00", 42),
        (DataType.UINT64, b"\x2a" + b"\x00" * 7, 42),
        (DataType.INT16, b"\xff\xff", -1),
        (DataType.INT32, b"\xff\xff\xff\xff", -1),
    ],
)
def test_typed_scalar_values(data_type: DataType, payload: bytes, expected: int) -> None:
    assert read_typed_value(ByteReader(payload), data_type) == expected


def test_typed_array_value() -> None:
    payload = struct.pack("<I", 3) + struct.pack("<HHH", 1, 2, 3)

    assert read_typed_value(ByteReader(payload), DataType.AUINT16) == (1, 2, 3)


def test_typed_string_value() -> None:
    assert read_typed_value(ByteReader(ptp_string("abc")), DataType.STR) == "abc"


def test_undefined_data_type_is_refused() -> None:
    with pytest.raises(ParseError, match="unsupported data type"):
        read_typed_value(ByteReader(b"\x00"), DataType.UNDEF)


@pytest.mark.parametrize("value", ["1234", (1, 2), -5, True])
def test_counter_coercion_refuses_anything_that_is_not_one_unsigned_integer(
    value: object,
) -> None:
    with pytest.raises(ParseError):
        coerce_counter(value)  # type: ignore[arg-type]


def test_counter_coercion_accepts_a_plain_integer() -> None:
    assert coerce_counter(0) == 0
    assert coerce_counter(123456) == 123456
