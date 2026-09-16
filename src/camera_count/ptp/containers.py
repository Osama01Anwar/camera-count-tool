"""PTP-over-USB container encode and decode.

A container is ``length(4) | type(2) | code(2) | transaction_id(4)`` followed by
a payload. Command containers carry up to five 32-bit parameters; data
containers carry the payload the operation defines.

Decoding is defensive: the length field arrives from an untrusted device, so it
is checked against the header size, against the real buffer size, and against
:data:`MAX_CONTAINER_LENGTH` before anything is sliced.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from camera_count.core.errors import ParseError
from camera_count.ptp.constants import (
    BULK_HEADER_LENGTH,
    MAX_COMMAND_PARAMETERS,
    MAX_CONTAINER_LENGTH,
    ContainerType,
)

_HEADER: Final = struct.Struct("<IHHI")
_UINT32: Final = struct.Struct("<I")

UINT32_MAX: Final = 0xFFFFFFFF


@dataclass(frozen=True, slots=True)
class Container:
    """One decoded PTP container."""

    container_type: ContainerType
    code: int
    transaction_id: int
    payload: bytes = b""

    @property
    def total_length(self) -> int:
        return BULK_HEADER_LENGTH + len(self.payload)

    def parameters(self) -> tuple[int, ...]:
        """The payload read as 32-bit parameters (command and response containers)."""
        usable = len(self.payload) - (len(self.payload) % 4)
        return tuple(_UINT32.unpack_from(self.payload, offset)[0] for offset in range(0, usable, 4))


def encode_command(code: int, transaction_id: int, parameters: Sequence[int] = ()) -> bytes:
    """Build a command container. Raises on anything the protocol cannot carry."""
    if not 0 <= code <= 0xFFFF:
        raise ParseError(f"operation code out of range: {code}")
    if not 0 <= transaction_id <= UINT32_MAX:
        raise ParseError(f"transaction id out of range: {transaction_id}")
    if len(parameters) > MAX_COMMAND_PARAMETERS:
        raise ParseError(
            f"a command container carries at most {MAX_COMMAND_PARAMETERS} parameters, "
            f"got {len(parameters)}"
        )
    for index, parameter in enumerate(parameters):
        if not 0 <= parameter <= UINT32_MAX:
            raise ParseError(f"parameter {index} out of 32-bit range: {parameter}")

    length = BULK_HEADER_LENGTH + 4 * len(parameters)
    header = _HEADER.pack(length, ContainerType.COMMAND.value, code, transaction_id)
    body = b"".join(_UINT32.pack(parameter) for parameter in parameters)
    return header + body


def decode_container(data: bytes) -> Container:
    """Decode one container from ``data``, checking every bound first."""
    if len(data) < BULK_HEADER_LENGTH:
        raise ParseError(
            f"container is shorter than the {BULK_HEADER_LENGTH}-byte header: {len(data)} bytes"
        )

    length, raw_type, code, transaction_id = _HEADER.unpack_from(data, 0)

    if length < BULK_HEADER_LENGTH:
        raise ParseError(f"container claims an impossible length: {length}")
    if length > MAX_CONTAINER_LENGTH:
        raise ParseError(f"container length {length} exceeds the {MAX_CONTAINER_LENGTH}-byte bound")
    if length > len(data):
        raise ParseError(f"container claims {length} bytes but only {len(data)} were received")

    try:
        container_type = ContainerType(raw_type)
    except ValueError as exc:
        raise ParseError(f"unknown container type 0x{raw_type:04X}") from exc

    return Container(
        container_type=container_type,
        code=code,
        transaction_id=transaction_id,
        payload=bytes(data[BULK_HEADER_LENGTH:length]),
    )


def split_containers(data: bytes) -> tuple[Container, ...]:
    """Decode consecutive containers from one buffer.

    Some transports hand back a data container and its response container in a
    single read. Anything left over that is too short to be a container is an
    error, not something to ignore.
    """
    containers: list[Container] = []
    offset = 0
    while offset < len(data):
        remaining = data[offset:]
        container = decode_container(remaining)
        containers.append(container)
        offset += container.total_length
    return tuple(containers)
