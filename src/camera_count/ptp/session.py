"""A read-only PTP session.

The session is the choke point: every operation passes through
:meth:`PtpSession.execute`, which checks the opcode against an allow-list
**before** handing anything to the transport, and records the exchange in the
transaction log. An adapter widens the allow-list with its own cited vendor read
operations and nothing else.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from types import TracebackType
from typing import Final

from camera_count.core.errors import ForbiddenOperationError, ProtocolError
from camera_count.diagnostics.log import TransactionLog
from camera_count.ptp.constants import (
    DEFAULT_TIMEOUT_MS,
    DataType,
    Operation,
    ResponseCode,
    operation_name,
    response_name,
)
from camera_count.ptp.parsers import (
    ByteReader,
    DeviceInfo,
    DevicePropertyDescription,
    parse_device_info,
    parse_device_property_description,
    read_typed_value,
)
from camera_count.ptp.transport import TransactionResult, Transport

#: The standard operations any session may use. All are reads.
BASE_READ_ONLY_OPERATIONS: Final[frozenset[int]] = frozenset(
    {
        Operation.GET_DEVICE_INFO.value,
        Operation.OPEN_SESSION.value,
        Operation.CLOSE_SESSION.value,
        Operation.GET_DEVICE_PROP_DESC.value,
        Operation.GET_DEVICE_PROP_VALUE.value,
    }
)


class PtpSession:
    """An open conversation with one camera, restricted to read operations."""

    def __init__(
        self,
        transport: Transport,
        *,
        allowed_opcodes: Iterable[int] = (),
        log: TransactionLog | None = None,
        session_id: int = 1,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self._transport = transport
        self._allowed = BASE_READ_ONLY_OPERATIONS | frozenset(allowed_opcodes)
        self._log = log if log is not None else TransactionLog(transport=transport.name)
        self._session_id = session_id
        self._timeout_ms = timeout_ms
        self._device_info: DeviceInfo | None = None
        self._opened = False

    # -- lifecycle ------------------------------------------------------------

    @property
    def log(self) -> TransactionLog:
        return self._log

    @property
    def allowed_opcodes(self) -> frozenset[int]:
        return self._allowed

    @property
    def is_open(self) -> bool:
        return self._opened

    def open(self) -> None:
        self._transport.open()
        result = self.execute(Operation.OPEN_SESSION.value, (self._session_id,))
        if result.response_code not in {
            ResponseCode.OK.value,
            ResponseCode.SESSION_ALREADY_OPENED.value,
        }:
            self._transport.close()
            raise ProtocolError(
                f"the camera refused to open a session: {response_name(result.response_code)}"
            )
        self._opened = True

    def close(self) -> None:
        try:
            if self._opened:
                self.execute(Operation.CLOSE_SESSION.value)
        except (ProtocolError, OSError):
            # A camera that has already gone away cannot refuse politely; the
            # transport is closed regardless.
            pass
        finally:
            self._opened = False
            self._transport.close()

    def __enter__(self) -> PtpSession:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # -- the choke point ------------------------------------------------------

    def execute(
        self,
        code: int,
        parameters: Sequence[int] = (),
        *,
        expect_data: bool = False,
        note: str | None = None,
    ) -> TransactionResult:
        """Run one operation, after checking it is on the allow-list."""
        if code not in self._allowed:
            self._log.record(
                operation=operation_name(code),
                opcode=code,
                parameters=tuple(parameters),
                response_name="REFUSED BY ALLOW-LIST",
                note="not sent: this operation is not on the read-only allow-list",
            )
            raise ForbiddenOperationError(
                f"operation {operation_name(code)} (0x{code:04X}) is not on the "
                "read-only allow-list and was not sent"
            )

        started = time.perf_counter()
        result = self._transport.transaction(
            code=code,
            parameters=tuple(parameters),
            expect_data=expect_data,
            timeout_ms=self._timeout_ms,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        self._log.record(
            operation=operation_name(code),
            opcode=code,
            parameters=tuple(parameters),
            response_code=result.response_code,
            response_name=response_name(result.response_code),
            response_parameters=result.response_parameters,
            data=result.data,
            duration_ms=elapsed_ms,
            note=note,
        )
        return result

    def execute_checked(
        self,
        code: int,
        parameters: Sequence[int] = (),
        *,
        expect_data: bool = False,
        note: str | None = None,
    ) -> TransactionResult:
        """Run an operation and raise unless the camera answered OK."""
        result = self.execute(code, parameters, expect_data=expect_data, note=note)
        if result.response_code != ResponseCode.OK.value:
            raise ProtocolError(
                f"{operation_name(code)} returned {response_name(result.response_code)}"
            )
        return result

    # -- standard reads -------------------------------------------------------

    def device_info(self, *, refresh: bool = False) -> DeviceInfo:
        """Fetch and cache DeviceInfo."""
        if self._device_info is None or refresh:
            result = self.execute_checked(
                Operation.GET_DEVICE_INFO.value, expect_data=True, note="identity"
            )
            self._device_info = parse_device_info(result.data)
            self._log.register_secret(self._device_info.serial_number)
        return self._device_info

    def property_description(self, property_code: int) -> DevicePropertyDescription:
        result = self.execute_checked(
            Operation.GET_DEVICE_PROP_DESC.value,
            (property_code,),
            expect_data=True,
            note=f"describe property 0x{property_code:04X}",
        )
        return parse_device_property_description(result.data)

    def property_value(
        self, property_code: int, data_type: DataType | None = None
    ) -> tuple[int | str | tuple[int, ...], str]:
        """Read a device property value.

        Returns the value and the transaction reference it came from, so the
        caller can tie any resulting reading to the exact bytes on the wire.
        When ``data_type`` is not given the description is fetched first: the
        width is taken from the device, never assumed.
        """
        if data_type is None:
            data_type = self.property_description(property_code).data_type

        result = self.execute_checked(
            Operation.GET_DEVICE_PROP_VALUE.value,
            (property_code,),
            expect_data=True,
            note=f"read property 0x{property_code:04X}",
        )
        reference = self._log.records[-1].reference
        value = read_typed_value(ByteReader(result.data, origin="DevicePropValue"), data_type)
        return value, reference

    def try_property_value(
        self, property_code: int, data_type: DataType | None = None
    ) -> tuple[int | str | tuple[int, ...], str] | None:
        """Read a property, returning None when the camera says it has none.

        A camera that answers DevicePropNotSupported is behaving correctly; that
        is an unavailable result, not a failure.
        """
        try:
            return self.property_value(property_code, data_type)
        except ProtocolError:
            return None
