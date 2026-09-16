"""The read-only guarantee, enforced before anything reaches the wire."""

from __future__ import annotations

import pytest

from camera_count.core.errors import ForbiddenOperationError, ProtocolError
from camera_count.diagnostics.log import TransactionLog
from camera_count.ptp.constants import DataType, Operation, ResponseCode
from camera_count.ptp.session import BASE_READ_ONLY_OPERATIONS, PtpSession
from camera_count.ptp.transport import TransactionResult
from tests.devmock.transport import (
    MockTransport,
    build_device_info,
    build_property_description,
)

# Operations that change the camera. None of these may ever be sent. Codes are
# from libgphoto2/camlibs/ptp2/ptp.h (InitiateCapture 0x100E, DeleteObject
# 0x100B, SetDevicePropValue 0x1016, FormatStore 0x100F, SendObject 0x100D).
WRITE_OPERATIONS = (0x100B, 0x100D, 0x100E, 0x100F, 0x1016)


def make_session(transport: MockTransport, **kwargs: object) -> PtpSession:
    return PtpSession(transport, log=TransactionLog(transport="mock"), **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("opcode", WRITE_OPERATIONS)
def test_write_operations_are_refused_before_transmission(opcode: int) -> None:
    transport = MockTransport()
    session = make_session(transport)

    with pytest.raises(ForbiddenOperationError):
        session.execute(opcode)

    assert transport.sent == [], "a refused operation must never reach the transport"


def test_refusal_is_recorded_in_the_transaction_log() -> None:
    transport = MockTransport()
    session = make_session(transport)

    with pytest.raises(ForbiddenOperationError):
        session.execute(0x100E)

    record = session.log.records[-1]
    assert record.response_name == "REFUSED BY ALLOW-LIST"
    assert record.note is not None
    assert "not sent" in record.note


def test_base_allow_list_contains_only_reads() -> None:
    expected_reads = {
        Operation.GET_DEVICE_INFO.value,
        Operation.OPEN_SESSION.value,
        Operation.CLOSE_SESSION.value,
        Operation.GET_DEVICE_PROP_DESC.value,
        Operation.GET_DEVICE_PROP_VALUE.value,
    }

    assert expected_reads == BASE_READ_ONLY_OPERATIONS
    for opcode in WRITE_OPERATIONS:
        assert opcode not in BASE_READ_ONLY_OPERATIONS


def test_adapter_may_widen_the_allow_list_but_not_beyond_it() -> None:
    transport = MockTransport()
    session = make_session(transport, allowed_opcodes={0x9999})

    session.execute(0x9999)
    assert transport.was_sent(0x9999)

    with pytest.raises(ForbiddenOperationError):
        session.execute(0x999A)


def test_transport_interface_offers_no_way_to_send_data() -> None:
    """The read-only guarantee is structural: there is no outbound data parameter."""
    import inspect

    from camera_count.ptp.transport import Transport

    signature = inspect.signature(Transport.transaction)
    assert set(signature.parameters) == {
        "self",
        "code",
        "parameters",
        "expect_data",
        "timeout_ms",
    }


# --- session lifecycle -------------------------------------------------------


def test_opening_a_session_sends_open_and_closing_sends_close() -> None:
    transport = MockTransport()
    session = make_session(transport)

    with session:
        assert transport.was_sent(Operation.OPEN_SESSION.value)

    assert transport.was_sent(Operation.CLOSE_SESSION.value)
    assert transport.closed


def test_a_refused_session_closes_the_transport() -> None:
    transport = MockTransport(
        responses={
            Operation.OPEN_SESSION.value: TransactionResult(
                response_code=ResponseCode.DEVICE_BUSY.value
            )
        }
    )
    session = make_session(transport)

    with pytest.raises(ProtocolError, match="refused to open a session"):
        session.open()

    assert transport.closed


def test_already_open_session_is_accepted() -> None:
    transport = MockTransport(
        responses={
            Operation.OPEN_SESSION.value: TransactionResult(
                response_code=ResponseCode.SESSION_ALREADY_OPENED.value
            )
        }
    )
    session = make_session(transport)

    session.open()

    assert session.is_open


# --- reads -------------------------------------------------------------------


def test_device_info_is_parsed_and_the_serial_is_registered_for_redaction() -> None:
    transport = MockTransport(
        responses={
            Operation.GET_DEVICE_INFO.value: TransactionResult(
                response_code=ResponseCode.OK.value,
                data=build_device_info(serial_number="MOCKSERIAL777"),
            )
        }
    )
    session = make_session(transport)

    info = session.device_info()

    assert info.manufacturer == "MOCK CAMERA - TEST ONLY"
    assert info.serial_number == "MOCKSERIAL777"
    exported = session.log.export(include_serials=False)
    assert "MOCKSERIAL777" not in str(exported)


def test_property_value_uses_the_width_the_device_reports() -> None:
    transport = MockTransport(
        responses={
            Operation.GET_DEVICE_PROP_DESC.value: TransactionResult(
                response_code=ResponseCode.OK.value,
                data=build_property_description(0xD1A3, DataType.UINT32.value),
            ),
            Operation.GET_DEVICE_PROP_VALUE.value: TransactionResult(
                response_code=ResponseCode.OK.value,
                data=(1234).to_bytes(4, "little"),
            ),
        }
    )
    session = make_session(transport)

    value, reference = session.property_value(0xD1A3)

    assert value == 1234
    assert session.log.find(reference) is not None


def test_unsupported_property_is_not_an_exception_for_the_caller() -> None:
    transport = MockTransport(
        responses={
            Operation.GET_DEVICE_PROP_DESC.value: TransactionResult(
                response_code=ResponseCode.DEVICE_PROP_NOT_SUPPORTED.value
            )
        }
    )
    session = make_session(transport)

    assert session.try_property_value(0xD1A3) is None
