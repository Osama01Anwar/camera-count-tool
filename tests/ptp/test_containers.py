"""Container encoding and the bounds that protect decoding."""

from __future__ import annotations

import struct

import pytest

from camera_count.core.errors import ParseError
from camera_count.ptp.constants import BULK_HEADER_LENGTH, MAX_CONTAINER_LENGTH, ContainerType
from camera_count.ptp.containers import (
    decode_container,
    encode_command,
    split_containers,
)
from tests.devmock.transport import build_container


def test_command_round_trip() -> None:
    raw = encode_command(0x1015, 7, (0xD1A3,))

    container = decode_container(raw)

    assert container.container_type is ContainerType.COMMAND
    assert container.code == 0x1015
    assert container.transaction_id == 7
    assert container.parameters() == (0xD1A3,)
    assert container.total_length == BULK_HEADER_LENGTH + 4


def test_command_with_no_parameters_is_header_only() -> None:
    raw = encode_command(0x1001, 1)

    assert len(raw) == BULK_HEADER_LENGTH
    assert decode_container(raw).parameters() == ()


@pytest.mark.parametrize(
    ("code", "transaction_id", "parameters", "message"),
    [
        (0x10000, 1, (), "operation code out of range"),
        (-1, 1, (), "operation code out of range"),
        (0x1001, 0x1_0000_0000, (), "transaction id out of range"),
        (0x1001, 1, (1, 2, 3, 4, 5, 6), "at most 5 parameters"),
        (0x1001, 1, (0x1_0000_0000,), "out of 32-bit range"),
    ],
)
def test_encoding_refuses_what_the_protocol_cannot_carry(
    code: int, transaction_id: int, parameters: tuple[int, ...], message: str
) -> None:
    with pytest.raises(ParseError, match=message):
        encode_command(code, transaction_id, parameters)


def test_short_buffer_is_refused() -> None:
    with pytest.raises(ParseError, match="shorter than"):
        decode_container(b"\x01\x02\x03")


def test_length_shorter_than_header_is_refused() -> None:
    raw = struct.pack("<IHHI", 4, ContainerType.DATA.value, 0x1001, 1)

    with pytest.raises(ParseError, match="impossible length"):
        decode_container(raw)


def test_length_beyond_the_bound_is_refused_without_allocating() -> None:
    raw = struct.pack("<IHHI", MAX_CONTAINER_LENGTH + 1, ContainerType.DATA.value, 0x1001, 1)

    with pytest.raises(ParseError, match="exceeds the"):
        decode_container(raw)


def test_length_longer_than_the_buffer_is_refused() -> None:
    raw = struct.pack("<IHHI", 4096, ContainerType.DATA.value, 0x1001, 1) + b"\x00" * 8

    with pytest.raises(ParseError, match="only 20 were received"):
        decode_container(raw)


def test_unknown_container_type_is_refused() -> None:
    raw = struct.pack("<IHHI", BULK_HEADER_LENGTH, 0x00FF, 0x1001, 1)

    with pytest.raises(ParseError, match="unknown container type"):
        decode_container(raw)


def test_split_reads_a_data_container_followed_by_its_response() -> None:
    data = build_container(ContainerType.DATA, 0x1015, 3, b"\x01\x02\x03\x04")
    response = build_container(ContainerType.RESPONSE, 0x2001, 3)

    containers = split_containers(data + response)

    assert [c.container_type for c in containers] == [
        ContainerType.DATA,
        ContainerType.RESPONSE,
    ]
    assert containers[0].payload == b"\x01\x02\x03\x04"


def test_trailing_garbage_is_an_error_not_something_to_ignore() -> None:
    data = build_container(ContainerType.DATA, 0x1015, 3, b"\x01")

    with pytest.raises(ParseError):
        split_containers(data + b"\x00\x01")
