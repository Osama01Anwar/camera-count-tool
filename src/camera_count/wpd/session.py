"""A read-only conversation with a camera through Windows Portable Devices.

Two ways in, both read-only:

* **Device properties.** Windows exposes a vendor-extended MTP device property
  as a WPD property whose key is the vendor GUID plus the MTP property code.
  A registry method of type ``ptp_property`` is read this way.
* **Vendor operation passthrough.** ``ptp_operation`` methods go through the
  MTP extension commands, using only the read-side command keys. The write-side
  keys are not defined anywhere in this package.

Windows owns the PTP session itself, so there is no OpenSession or CloseSession
here. Identity comes from the standard WPD device properties rather than from a
DeviceInfo dataset.
"""

from __future__ import annotations

import contextlib
import time
from types import TracebackType
from typing import Any, Final

from camera_count.core.enums import Protocol
from camera_count.core.errors import (
    DeviceAccessError,
    ForbiddenOperationError,
    ParseError,
    ProtocolError,
)
from camera_count.core.models import CameraIdentity
from camera_count.diagnostics.log import TransactionLog
from camera_count.ptp.constants import MAX_CONTAINER_LENGTH, ResponseCode, response_name
from camera_count.ptp.transport import TransactionResult
from camera_count.wpd import constants as keys
from camera_count.wpd.constants import PropertyKey

CLIENT_NAME: Final = "Camera Count Tool"
CLIENT_MAJOR: Final = 0
CLIENT_MINOR: Final = 1
CLIENT_REVISION: Final = 0


class WpdSession:
    """An open, read-only WPD connection to one camera."""

    def __init__(
        self,
        device_id: str,
        *,
        allowed_opcodes: frozenset[int] = frozenset(),
        log: TransactionLog | None = None,
        timeout_ms: int = 5_000,
    ) -> None:
        self._device_id = device_id
        self._allowed = frozenset(allowed_opcodes)
        self._log = log if log is not None else TransactionLog(transport="wpd")
        self._timeout_ms = timeout_ms
        self._device: Any = None
        self._properties: Any = None
        self._identity: CameraIdentity | None = None

    # -- lifecycle ------------------------------------------------------------

    @property
    def name(self) -> str:
        return "wpd"

    @property
    def log(self) -> TransactionLog:
        return self._log

    @property
    def allowed_opcodes(self) -> frozenset[int]:
        return self._allowed

    @property
    def is_open(self) -> bool:
        return self._device is not None

    def permit_operations(self, opcodes: frozenset[int]) -> None:
        """Widen the allow-list to one adapter's cited vendor read operations.

        Recorded in the log, because a change to what this program may send is
        exactly the kind of thing a reader of the log should be able to see.
        """
        added = frozenset(opcodes) - self._allowed
        if not added:
            return
        self._allowed = self._allowed | added
        self._log.record(
            operation="allow-list widened",
            opcode=0,
            response_name="OK",
            note="permitted vendor read operations: "
            + ", ".join(f"0x{code:04X}" for code in sorted(added)),
        )

    def open(self) -> None:
        try:
            import comtypes  # noqa: PLC0415
            import comtypes.client  # noqa: PLC0415

            comtypes.CoInitialize()
            comtypes.client.GetModule("portabledeviceapi.dll")
            comtypes.client.GetModule("portabledevicetypes.dll")
            from comtypes.gen import PortableDeviceApiLib as api  # noqa: PLC0415
            from comtypes.gen import PortableDeviceTypesLib as types  # noqa: PLC0415

            client_info = comtypes.client.CreateObject(
                types.PortableDeviceValues, interface=api.IPortableDeviceValues
            )
            _set_client_info(client_info, api)

            device = comtypes.client.CreateObject(api.PortableDevice, interface=api.IPortableDevice)
            device.Open(self._device_id, client_info)
            self._device = device
            self._properties = device.Content().Properties()
        except Exception as exc:  # noqa: BLE001 - a busy camera must produce a reason
            raise DeviceAccessError(
                "the camera could not be opened. Close File Explorer or any other "
                f"program showing it and try again. Windows reported: {exc}"
            ) from exc

    def close(self) -> None:
        device, self._device = self._device, None
        self._properties = None
        if device is not None:
            # A camera that has already been unplugged cannot say goodbye.
            with contextlib.suppress(Exception):
                device.Close()

    def __enter__(self) -> WpdSession:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # -- identity -------------------------------------------------------------

    def identity(self) -> CameraIdentity:
        """Read manufacturer, model, serial and firmware from WPD properties."""
        if self._identity is not None:
            return self._identity

        started = time.perf_counter()
        values = self._read_device_properties(
            (
                keys.DEVICE_MANUFACTURER,
                keys.DEVICE_MODEL,
                keys.DEVICE_SERIAL_NUMBER,
                keys.DEVICE_FIRMWARE_VERSION,
            )
        )
        identity = CameraIdentity(
            manufacturer=values.get(keys.DEVICE_MANUFACTURER.as_tuple()),
            model=values.get(keys.DEVICE_MODEL.as_tuple()),
            serial=values.get(keys.DEVICE_SERIAL_NUMBER.as_tuple()),
            firmware=values.get(keys.DEVICE_FIRMWARE_VERSION.as_tuple()),
            protocol=Protocol.MTP_WPD,
        )
        self._log.record(
            operation="WPD device identity",
            opcode=0,
            response_name="OK",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            note=f"read from {keys.DEVICE_MANUFACTURER.citation}",
        )
        self._log.register_secret(identity.serial)
        self._identity = identity
        return identity

    def _read_device_properties(
        self, wanted: tuple[PropertyKey, ...]
    ) -> dict[tuple[str, int], str | None]:
        if self._properties is None:
            raise ProtocolError("the WPD session is not open")

        import comtypes  # noqa: PLC0415
        import comtypes.client  # noqa: PLC0415
        from comtypes.gen import PortableDeviceApiLib as api  # noqa: PLC0415
        from comtypes.gen import PortableDeviceTypesLib as types  # noqa: PLC0415

        key_collection = comtypes.client.CreateObject(
            types.PortableDeviceKeyCollection, interface=api.IPortableDeviceKeyCollection
        )
        for key in wanted:
            key_collection.Add(_propertykey(key, api))

        values = self._properties.GetValues(keys.DEVICE_OBJECT_ID, key_collection)
        result: dict[tuple[str, int], str | None] = {}
        for key in wanted:
            result[key.as_tuple()] = _string_value(values, _propertykey(key, api))
        return result

    # -- counter reads --------------------------------------------------------

    def read_device_property(self, mtp_property_code: int) -> tuple[int, str] | None:
        """Read a vendor-extended MTP device property as an unsigned integer.

        Returns the value and the transaction reference, or ``None`` when the
        camera does not expose that property. A property that is present but is
        not a single unsigned integer is a parse failure, not something to
        reinterpret.
        """
        if self._properties is None:
            raise ProtocolError("the WPD session is not open")

        import comtypes  # noqa: PLC0415
        import comtypes.client  # noqa: PLC0415
        from comtypes.gen import PortableDeviceApiLib as api  # noqa: PLC0415
        from comtypes.gen import PortableDeviceTypesLib as types  # noqa: PLC0415

        key = keys.vendor_device_property_key(mtp_property_code)
        started = time.perf_counter()

        key_collection = comtypes.client.CreateObject(
            types.PortableDeviceKeyCollection, interface=api.IPortableDeviceKeyCollection
        )
        key_collection.Add(_propertykey(key, api))

        try:
            values = self._properties.GetValues(keys.DEVICE_OBJECT_ID, key_collection)
            raw = values.GetUnsignedIntegerValue(_propertykey(key, api))
        except Exception as exc:  # noqa: BLE001 - absence is an answer, not a crash
            self._log.record(
                operation=f"WPD device property 0x{mtp_property_code:04X}",
                opcode=mtp_property_code,
                response_name="NOT PROVIDED",
                duration_ms=(time.perf_counter() - started) * 1000.0,
                note=f"the camera did not provide this property: {exc}",
            )
            return None

        value = int(raw)
        record = self._log.record(
            operation=f"WPD device property 0x{mtp_property_code:04X}",
            opcode=mtp_property_code,
            response_name="OK",
            data=value.to_bytes(4, "little", signed=False) if value <= 0xFFFFFFFF else b"",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            note=f"key {key} ({key.citation})",
        )
        if value < 0:
            raise ParseError(f"a counter must not be negative, got {value}")
        return value, record.reference

    def execute_read_operation(
        self, code: int, parameters: tuple[int, ...] = (), *, expect_data: bool = False
    ) -> TransactionResult:
        """Send a vendor operation through the MTP read-side passthrough."""
        if code not in self._allowed:
            self._log.record(
                operation=f"vendor operation 0x{code:04X}",
                opcode=code,
                parameters=parameters,
                response_name="REFUSED BY ALLOW-LIST",
                note="not sent: this operation is not on the read-only allow-list",
            )
            raise ForbiddenOperationError(
                f"vendor operation 0x{code:04X} is not on the read-only allow-list and was not sent"
            )
        if self._device is None:
            raise ProtocolError("the WPD session is not open")

        started = time.perf_counter()
        try:
            response_code, response_params, data = self._passthrough(
                code, parameters, expect_data=expect_data
            )
        except DeviceAccessError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface the reason, never a number
            raise ProtocolError(f"the vendor operation failed: {exc}") from exc

        self._log.record(
            operation=f"vendor operation 0x{code:04X}",
            opcode=code,
            parameters=parameters,
            response_code=response_code,
            response_name=response_name(response_code),
            response_parameters=response_params,
            data=data,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            note=f"via {keys.COMMAND_EXECUTE_WITH_DATA_TO_READ.citation}",
        )
        return TransactionResult(
            response_code=response_code, response_parameters=response_params, data=data
        )

    def _passthrough(
        self, code: int, parameters: tuple[int, ...], *, expect_data: bool
    ) -> tuple[int, tuple[int, ...], bytes]:
        import comtypes  # noqa: PLC0415
        import comtypes.client  # noqa: PLC0415
        from comtypes.gen import PortableDeviceApiLib as api  # noqa: PLC0415
        from comtypes.gen import PortableDeviceTypesLib as types  # noqa: PLC0415

        command = (
            keys.COMMAND_EXECUTE_WITH_DATA_TO_READ
            if expect_data
            else (keys.COMMAND_EXECUTE_WITHOUT_DATA_PHASE)
        )
        params = _command_values(command, api, types, comtypes)
        params.SetUnsignedIntegerValue(_propertykey(keys.PROPERTY_OPERATION_CODE, api), code)
        params.SetIUnknownValue(
            _propertykey(keys.PROPERTY_OPERATION_PARAMS, api),
            _uint_collection(parameters, api, types, comtypes),
        )

        results = self._device.SendCommand(0, params)
        if not expect_data:
            return (
                int(
                    results.GetUnsignedIntegerValue(_propertykey(keys.PROPERTY_RESPONSE_CODE, api))
                ),
                (),
                b"",
            )

        context = results.GetStringValue(_propertykey(keys.PROPERTY_TRANSFER_CONTEXT, api))
        total = int(
            results.GetUnsignedLargeIntegerValue(
                _propertykey(keys.PROPERTY_TRANSFER_TOTAL_DATA_SIZE, api)
            )
        )
        if total > MAX_CONTAINER_LENGTH:
            self._end_transfer(context, api, types, comtypes)
            raise ParseError(
                f"the camera offered {total} bytes, over the {MAX_CONTAINER_LENGTH}-byte bound"
            )

        data = self._read_all(context, total, api, types, comtypes)
        response_code, response_params = self._end_transfer(context, api, types, comtypes)
        return response_code, response_params, data

    def _read_all(self, context: str, total: int, api: Any, types: Any, comtypes: Any) -> bytes:
        chunks: list[bytes] = []
        remaining = total
        while remaining > 0:
            wanted = min(remaining, keys.DEFAULT_CHUNK_BYTES)
            params = _command_values(keys.COMMAND_READ_DATA, api, types, comtypes)
            params.SetStringValue(_propertykey(keys.PROPERTY_TRANSFER_CONTEXT, api), context)
            params.SetUnsignedIntegerValue(
                _propertykey(keys.PROPERTY_TRANSFER_NUM_BYTES_TO_READ, api), wanted
            )
            params.SetBufferValue(
                _propertykey(keys.PROPERTY_TRANSFER_DATA, api), bytes(wanted), wanted
            )

            results = self._device.SendCommand(0, params)
            read = int(
                results.GetUnsignedIntegerValue(
                    _propertykey(keys.PROPERTY_TRANSFER_NUM_BYTES_READ, api)
                )
            )
            if read <= 0:
                break
            chunk = bytes(results.GetBufferValue(_propertykey(keys.PROPERTY_TRANSFER_DATA, api)))[
                :read
            ]
            chunks.append(chunk)
            remaining -= read
        return b"".join(chunks)

    def _end_transfer(
        self, context: str, api: Any, types: Any, comtypes: Any
    ) -> tuple[int, tuple[int, ...]]:
        params = _command_values(keys.COMMAND_END_DATA_TRANSFER, api, types, comtypes)
        params.SetStringValue(_propertykey(keys.PROPERTY_TRANSFER_CONTEXT, api), context)
        results = self._device.SendCommand(0, params)
        try:
            code = int(
                results.GetUnsignedIntegerValue(_propertykey(keys.PROPERTY_RESPONSE_CODE, api))
            )
        except Exception:  # noqa: BLE001 - a silent end is reported as undefined
            code = ResponseCode.UNDEFINED.value
        return code, ()


# --- COM helpers -------------------------------------------------------------


def _propertykey(key: PropertyKey, api: Any) -> Any:
    """Build a WPD PROPERTYKEY structure from our own constant."""
    import comtypes  # noqa: PLC0415

    property_key = api._tagpropertykey()  # noqa: SLF001 - the generated struct name
    property_key.fmtid = comtypes.GUID("{" + key.fmtid + "}")
    property_key.pid = key.pid
    return property_key


def _set_client_info(values: Any, api: Any) -> None:
    """Identify this client to Windows, and ask for read access only.

    WPD_CLIENT_DESIRED_ACCESS is set to GENERIC_READ, so the read-only
    guarantee is declared to the operating system at connection time rather
    than only being enforced inside this program.
    """
    values.SetStringValue(_propertykey(keys.CLIENT_NAME_KEY, api), CLIENT_NAME)
    values.SetUnsignedIntegerValue(_propertykey(keys.CLIENT_MAJOR_VERSION_KEY, api), CLIENT_MAJOR)
    values.SetUnsignedIntegerValue(_propertykey(keys.CLIENT_MINOR_VERSION_KEY, api), CLIENT_MINOR)
    values.SetUnsignedIntegerValue(_propertykey(keys.CLIENT_REVISION_KEY, api), CLIENT_REVISION)
    values.SetUnsignedIntegerValue(
        _propertykey(keys.CLIENT_DESIRED_ACCESS_KEY, api), keys.GENERIC_READ
    )


def _command_values(command: PropertyKey, api: Any, types: Any, comtypes: Any) -> Any:
    """Create an IPortableDeviceValues carrying one command's category and id."""
    values = comtypes.client.CreateObject(
        types.PortableDeviceValues, interface=api.IPortableDeviceValues
    )
    values.SetGuidValue(
        _propertykey(keys.PROPERTY_COMMON_COMMAND_CATEGORY, api),
        comtypes.GUID("{" + command.fmtid + "}"),
    )
    values.SetUnsignedIntegerValue(_propertykey(keys.PROPERTY_COMMON_COMMAND_ID, api), command.pid)
    return values


def _uint_collection(values: tuple[int, ...], api: Any, types: Any, comtypes: Any) -> Any:
    collection = comtypes.client.CreateObject(
        types.PortableDevicePropVariantCollection,
        interface=api.IPortableDevicePropVariantCollection,
    )
    for value in values:
        collection.Add(_uint_propvariant(value, api))
    return collection


def _uint_propvariant(value: int, api: Any) -> Any:
    variant = api.tag_inner_PROPVARIANT()
    variant.vt = 19  # VT_UI4
    variant.__MIDL____MIDL_itf_PortableDeviceApi_0001_00000001.ulVal = value
    return variant


def _string_value(values: Any, property_key: Any) -> str | None:
    try:
        raw = values.GetStringValue(property_key)
    except Exception:  # noqa: BLE001 - an absent field stays absent
        return None
    text = str(raw).strip()
    return text or None
