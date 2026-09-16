"""Property-based fuzzing of every parser that touches device bytes.

The contract is narrow and absolute: given any byte string at all, a parser
either returns a value or raises ParseError. It never raises anything else,
never hangs, and never allocates on a length it read off the wire.
"""

from __future__ import annotations

import struct

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from camera_count.core.errors import ParseError
from camera_count.ptp.constants import DataType
from camera_count.ptp.containers import decode_container, split_containers
from camera_count.ptp.parsers import (
    ByteReader,
    parse_device_info,
    parse_device_property_description,
    read_typed_value,
)

ARBITRARY = st.binary(min_size=0, max_size=4096)
FUZZ = settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@FUZZ
@given(ARBITRARY)
def test_container_decoding_only_ever_raises_parse_error(data: bytes) -> None:
    try:
        container = decode_container(data)
    except ParseError:
        return
    assert container.total_length <= len(data)
    container.parameters()


@FUZZ
@given(ARBITRARY)
def test_container_splitting_only_ever_raises_parse_error(data: bytes) -> None:
    try:
        containers = split_containers(data)
    except ParseError:
        return
    assert sum(c.total_length for c in containers) == len(data)


@FUZZ
@given(ARBITRARY)
def test_device_info_parsing_only_ever_raises_parse_error(data: bytes) -> None:
    try:
        info = parse_device_info(data)
    except ParseError:
        return
    assert isinstance(info.model, str)
    assert len(info.operations_supported) <= 65_536


@FUZZ
@given(ARBITRARY)
def test_property_description_parsing_only_ever_raises_parse_error(data: bytes) -> None:
    try:
        parse_device_property_description(data)
    except ParseError:
        return


@FUZZ
@given(ARBITRARY, st.sampled_from(list(DataType)))
def test_typed_value_reading_only_ever_raises_parse_error(data: bytes, data_type: DataType) -> None:
    try:
        read_typed_value(ByteReader(data), data_type)
    except ParseError:
        return


@FUZZ
@given(st.lists(st.integers(min_value=0, max_value=255), min_size=0, max_size=64))
def test_reader_never_returns_more_bytes_than_it_was_given(values: list[int]) -> None:
    data = bytes(values)
    reader = ByteReader(data)
    taken = 0
    while reader.remaining:
        chunk = reader.take(1)
        taken += len(chunk)
    assert taken == len(data)


@FUZZ
@given(st.integers(min_value=0, max_value=0xFFFFFFFF))
def test_a_declared_array_count_never_drives_allocation(count: int) -> None:
    """A huge declared count must fail fast, not try to build the list."""
    payload = struct.pack("<I", count)
    try:
        result = ByteReader(payload).uint32_array()
    except ParseError:
        return
    assert result == ()
