"""One inspection, end to end.

Detect a camera, identify it, look it up in the registry, and ask the matching
adapter for whatever counters are documented. Every step that stops short
produces a reason, and every counter comes back either as an exact reading with
a citation or as NOT AVAILABLE.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from camera_count.adapters import select_adapter
from camera_count.adapters.base import RegistryAdapter
from camera_count.core.errors import DeviceAccessError, ProtocolError
from camera_count.core.messages import (
    CAMERA_MODEL_NOT_IDENTIFIED,
    CAMERA_NOT_ACCESSIBLE,
    EXACT_COUNT_UNAVAILABLE,
    PROTOCOL_NOT_SUPPORTED,
    REASON_DEVICE_BUSY,
    REASON_MASS_STORAGE,
    REASON_MODEL_UNKNOWN,
    REASON_NO_DEVICE,
    VERIFIED_EXACT_COUNT,
)
from camera_count.core.models import (
    CameraIdentity,
    CounterSlot,
    CountResult,
    ShutterReading,
    Unavailable,
    build_counter_slots,
)
from camera_count.diagnostics.log import TransactionLog
from camera_count.link import CameraLink
from camera_count.registry import CameraRegistry, load_default_registry
from camera_count.registry.models import CameraModel
from camera_count.usb.enumerate import DetectionReport, detect
from camera_count.usb.models import UsbDeviceInfo

LinkFactory = Callable[[UsbDeviceInfo, RegistryAdapter, TransactionLog], CameraLink]


@dataclass(frozen=True, slots=True)
class InspectionResult:
    """Everything one inspection established."""

    identity: CameraIdentity = field(default_factory=CameraIdentity)
    device: UsbDeviceInfo | None = None
    model: CameraModel | None = None
    adapter: str = "none"
    results: tuple[CountResult, ...] = ()
    counters: tuple[CounterSlot, ...] = ()
    log: TransactionLog = field(default_factory=TransactionLog)
    detection: DetectionReport | None = None
    failure: Unavailable | None = None

    @property
    def exact_reading(self) -> ShutterReading | None:
        for slot in self.counters:
            if isinstance(slot.result, ShutterReading):
                return slot.result
        return None

    @property
    def has_exact_count(self) -> bool:
        return self.exact_reading is not None

    @property
    def headline(self) -> str:
        return VERIFIED_EXACT_COUNT if self.has_exact_count else EXACT_COUNT_UNAVAILABLE

    @property
    def exit_code(self) -> int:
        """0 an exact count was found, 2 none is available. Never an error."""
        return 0 if self.has_exact_count else 2


def _first_usable_camera(
    report: DetectionReport,
) -> tuple[UsbDeviceInfo | None, Unavailable | None]:
    """Choose a camera to talk to, or explain why none can be used."""
    if not report.cameras:
        return None, Unavailable(message=CAMERA_NOT_ACCESSIBLE, reason=REASON_NO_DEVICE)

    for camera in report.cameras:
        if camera.is_accessible and not camera.is_mass_storage_only:
            return camera, None

    blocked = report.blocked_cameras
    if blocked:
        holder = blocked[0].claimed_by or "another program"
        return None, Unavailable(
            message=CAMERA_NOT_ACCESSIBLE,
            reason=f"{REASON_DEVICE_BUSY} It is held by {holder}",
        )

    if report.mass_storage_cameras:
        return None, Unavailable(message=PROTOCOL_NOT_SUPPORTED, reason=REASON_MASS_STORAGE)

    return None, Unavailable(message=CAMERA_NOT_ACCESSIBLE, reason=REASON_NO_DEVICE)


def default_link_factory(
    device: UsbDeviceInfo, adapter: RegistryAdapter, log: TransactionLog
) -> CameraLink:
    """Open a Windows Portable Devices session for a detected camera."""
    from camera_count.wpd.session import WpdSession  # noqa: PLC0415

    session = WpdSession(device.address, allowed_opcodes=adapter.allowed_opcodes, log=log)
    session.open()
    return session


def inspect_camera(
    *,
    registry: CameraRegistry | None = None,
    detection: DetectionReport | None = None,
    link_factory: LinkFactory | None = None,
) -> InspectionResult:
    """Run a full inspection of the first usable camera."""
    registry = registry or load_default_registry()
    report = detection if detection is not None else detect()

    device, failure = _first_usable_camera(report)
    if device is None:
        return InspectionResult(detection=report, failure=failure)

    log = TransactionLog(transport=device.backend)
    factory = link_factory or default_link_factory

    # The link starts with no vendor operations permitted. It is widened once,
    # after the model is known, and only to what that model's adapter cites.
    identity_only = select_adapter(None)
    try:
        link = factory(device, identity_only, log)
    except DeviceAccessError as exc:
        return InspectionResult(
            device=device,
            detection=report,
            log=log,
            failure=Unavailable(message=CAMERA_NOT_ACCESSIBLE, reason=str(exc)),
        )

    try:
        identity = link.identity()
        entry = registry.find_entry(identity.manufacturer) if identity.manufacturer else None
        model = registry.find_model(identity.manufacturer, identity.model)
        adapter = select_adapter(entry)

        permit = getattr(link, "permit_operations", None)
        if permit is not None and adapter.allowed_opcodes:
            permit(adapter.allowed_opcodes)

        if not identity.model:
            failure = Unavailable(message=CAMERA_MODEL_NOT_IDENTIFIED, reason=REASON_MODEL_UNKNOWN)
            return InspectionResult(
                identity=identity,
                device=device,
                detection=report,
                adapter=adapter.name,
                log=log,
                failure=failure,
            )

        results = adapter.read_counts(link, model, identity)
    except ProtocolError as exc:
        return InspectionResult(
            device=device,
            detection=report,
            log=log,
            failure=Unavailable(message=CAMERA_NOT_ACCESSIBLE, reason=str(exc)),
        )
    finally:
        closer = getattr(link, "close", None)
        if callable(closer):
            closer()

    return InspectionResult(
        identity=identity,
        device=device,
        model=model,
        adapter=adapter.name,
        results=results,
        counters=build_counter_slots(results),
        log=log,
        detection=report,
    )
