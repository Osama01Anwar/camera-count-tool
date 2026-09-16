"""Device detection across whichever backends this machine offers."""

from __future__ import annotations

import platform
from dataclasses import dataclass

from camera_count.core.enums import Protocol
from camera_count.usb.backend import EnumerationBackend, EnumerationResult
from camera_count.usb.libusb_backend import LibusbBackend
from camera_count.usb.models import UsbDeviceInfo
from camera_count.usb.wpd_backend import WpdBackend


def default_backends() -> tuple[EnumerationBackend, ...]:
    """Backends to try on this platform, in order of preference.

    On Windows, WPD comes first: it is the supported way to reach a camera
    without replacing the driver Windows installed. libusb is still tried,
    because a user who has deliberately installed WinUSB for a device should
    get the benefit of it - this program never installs one itself.
    """
    if platform.system() == "Windows":
        return (WpdBackend(), LibusbBackend())
    return (LibusbBackend(),)


@dataclass(frozen=True, slots=True)
class DetectionReport:
    """Everything detection found, including why a backend could not run."""

    results: tuple[EnumerationResult, ...] = ()
    devices: tuple[UsbDeviceInfo, ...] = ()
    cameras: tuple[UsbDeviceInfo, ...] = ()

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(warning for result in self.results for warning in result.warnings)

    @property
    def unavailable_backends(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (result.backend, result.unavailable_reason or "unavailable")
            for result in self.results
            if not result.available
        )

    @property
    def has_camera(self) -> bool:
        return bool(self.cameras)

    @property
    def blocked_cameras(self) -> tuple[UsbDeviceInfo, ...]:
        """Cameras that were seen but are being held by something else."""
        return tuple(camera for camera in self.cameras if not camera.is_accessible)

    @property
    def mass_storage_cameras(self) -> tuple[UsbDeviceInfo, ...]:
        return tuple(camera for camera in self.cameras if camera.is_mass_storage_only)


def is_camera_candidate(device: UsbDeviceInfo, known_vendor_ids: frozenset[int]) -> bool:
    """Decide whether a device is worth talking to.

    Two grounds, both evidence-based: it advertises the USB Still Image class,
    or its USB vendor id belongs to a camera manufacturer in the registry. A
    phone on the same bus satisfies neither.
    """
    if device.is_still_image_device:
        return True
    if device.vendor_id in known_vendor_ids:
        return True
    return device.protocol is Protocol.MTP_WPD and device.vendor_id in known_vendor_ids


def detect(
    *,
    backends: tuple[EnumerationBackend, ...] | None = None,
    known_vendor_ids: frozenset[int] | None = None,
) -> DetectionReport:
    """Enumerate devices and pick out the camera candidates."""
    if known_vendor_ids is None:
        from camera_count.registry import load_default_registry  # noqa: PLC0415

        known_vendor_ids = frozenset(load_default_registry().vendor_ids())

    chosen = backends if backends is not None else default_backends()
    results = tuple(backend.enumerate() for backend in chosen)

    devices: list[UsbDeviceInfo] = []
    seen: set[tuple[int, int, str]] = set()
    for result in results:
        for device in result.devices:
            key = (device.vendor_id, device.product_id, device.address)
            if key in seen:
                continue
            seen.add(key)
            devices.append(device)

    cameras = tuple(device for device in devices if is_camera_candidate(device, known_vendor_ids))
    return DetectionReport(results=results, devices=tuple(devices), cameras=cameras)
