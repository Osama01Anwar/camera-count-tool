"""The adapter mechanism.

An adapter does not know any camera secrets. Everything it reads comes from the
registry entry for the identified model, and the registry only holds methods
that carry a citation. That keeps the per-manufacturer modules thin - they
declare who they are and which vendor read operations they are permitted to
send - and keeps the knowledge in data that a contributor can review.

If no method applies, the adapter returns an unavailable result with the reason.
It never falls back to another field, another model's method, or a number that
happens to be lying around.
"""

from __future__ import annotations

from typing import ClassVar

from camera_count.core.enums import MethodType, ValueSource
from camera_count.core.errors import ParseError, ProtocolError
from camera_count.core.messages import (
    CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT,
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    REASON_DEVICE_REFUSED,
    REASON_NO_REGISTRY_ENTRY,
)
from camera_count.core.models import CameraIdentity, CountResult, ShutterReading, Unavailable
from camera_count.link import CameraLink
from camera_count.ptp.constants import ResponseCode
from camera_count.ptp.parsers import ByteReader
from camera_count.registry.firmware import firmware_matches
from camera_count.registry.models import CameraModel, ManufacturerEntry, RegisteredMethod

REASON_FILE_METHOD_ONLY = (
    "The documented method for this model reads an original image file, not the "
    "camera. Run: camera-count exif <original file>."
)
REASON_NOT_EXPOSED = "The camera did not expose the documented property while connected this way."
REASON_SERVICE_INTERFACE = (
    "The documented method needs the manufacturer's service interface, which this "
    "program does not use."
)


class RegistryAdapter:
    """Reads whatever the registry documents for the identified model."""

    #: Must equal the ``manufacturer`` field of the registry file it serves.
    manufacturer_key: ClassVar[str] = ""

    #: Vendor operation codes this adapter may send. Each one needs a citation
    #: in the registry and must be a read. Empty means no vendor operation at
    #: all, which is the correct default.
    vendor_read_opcodes: ClassVar[frozenset[int]] = frozenset()

    #: Free-text note shown in reports for cameras of this make.
    limitations: ClassVar[tuple[str, ...]] = ()

    @property
    def name(self) -> str:
        return self.manufacturer_key or "generic"

    @property
    def allowed_opcodes(self) -> frozenset[int]:
        return self.vendor_read_opcodes

    def matches(self, entry: ManufacturerEntry | None) -> bool:
        """True when this adapter serves the registry entry that was found."""
        if entry is None:
            return False
        return entry.manufacturer.casefold() == self.manufacturer_key.casefold()

    # -- reading --------------------------------------------------------------

    def read_counts(
        self,
        link: CameraLink,
        model: CameraModel | None,
        identity: CameraIdentity,
    ) -> tuple[CountResult, ...]:
        """Read every documented counter for this model, in registry order."""
        if model is None:
            return (
                Unavailable(
                    message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                    reason=REASON_NO_REGISTRY_ENTRY,
                ),
            )

        trusted = model.trusted_methods()
        if not trusted:
            return (
                Unavailable(
                    message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                    reason=REASON_NO_REGISTRY_ENTRY,
                ),
            )

        camera_methods = [method for method in trusted if method.is_camera_method]
        if not camera_methods:
            return (
                Unavailable(
                    message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                    reason=REASON_FILE_METHOD_ONLY,
                ),
            )

        return tuple(self._read_method(link, method, identity) for method in camera_methods)

    def _read_method(
        self, link: CameraLink, method: RegisteredMethod, identity: CameraIdentity
    ) -> CountResult:
        if not firmware_matches(method.firmware_range, identity.firmware):
            return Unavailable(
                message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                reason=(
                    f"The documented method applies to firmware "
                    f"{method.firmware_range}; this camera reports "
                    f"{identity.display_firmware()}."
                ),
                count_type=method.count_type,
            )

        if method.method_type is MethodType.SERVICE_INTERFACE:
            return Unavailable(
                message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                reason=REASON_SERVICE_INTERFACE,
                count_type=method.count_type,
            )

        code = method.numeric_identifier()
        if code is None:
            return Unavailable(
                message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                reason=(
                    f"The registry identifier {method.identifier!r} is not a numeric "
                    "code, so it cannot be read from the camera."
                ),
                count_type=method.count_type,
            )

        try:
            answer = (
                self._read_property(link, code)
                if method.method_type is MethodType.PTP_PROPERTY
                else self._read_operation(link, code, method)
            )
        except (ProtocolError, ParseError) as exc:
            return Unavailable(
                message=CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT,
                reason=f"{REASON_DEVICE_REFUSED} {exc}",
                count_type=method.count_type,
            )

        if answer is None:
            return Unavailable(
                message=CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT,
                reason=REASON_NOT_EXPOSED,
                count_type=method.count_type,
            )

        value, reference = answer
        if method.is_invalid_value(value):
            return Unavailable(
                message=CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT,
                reason=(
                    f"The camera returned {value}, which the documented source records "
                    "as 'not available' rather than as a count."
                ),
                count_type=method.count_type,
            )
        return ShutterReading.from_source(
            value=value, source_id=method.source_id, transaction_ref=reference
        )

    @staticmethod
    def _read_property(link: CameraLink, code: int) -> tuple[int, str] | None:
        return link.read_device_property(code)

    @staticmethod
    def _read_operation(
        link: CameraLink, code: int, method: RegisteredMethod
    ) -> tuple[int, str] | None:
        spec = method.value_spec
        if spec is None:
            # The loader refuses such an entry, so this is defence in depth.
            raise ParseError("the registry method does not say where the integer is in the answer")

        wants_data = spec.source is ValueSource.DATA_UINT32
        result = link.execute_read_operation(code, (), expect_data=wants_data)
        if result.response_code != ResponseCode.OK.value:
            return None

        reference = link.log.records[-1].reference
        if spec.source is ValueSource.RESPONSE_PARAMETER:
            if spec.index >= len(result.response_parameters):
                raise ParseError(
                    f"the camera returned {len(result.response_parameters)} response "
                    f"parameters; the documented method reads parameter {spec.index}"
                )
            return result.response_parameters[spec.index], reference

        reader = ByteReader(result.data, origin=f"operation 0x{code:04X}")
        reader.take(spec.offset)
        return reader.u32(), reference
