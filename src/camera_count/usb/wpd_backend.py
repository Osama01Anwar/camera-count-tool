"""Enumeration through Windows Portable Devices (WPD).

On Windows a camera in PTP or MTP mode is claimed by the system's portable
device driver, so libusb cannot open it without replacing that driver. This
program never replaces a driver. It talks to the device through WPD instead,
which is the supported path and leaves the user's system exactly as it was.

The device id string WPD reports carries the USB vendor and product ids, for
example::

    \\\\?\\usb#vid_04b0&pid_0428#0123456789#{6ac27878-a6fa-4155-ba85-f98f491d4f33}

so ids come from the identifier itself rather than from a guess.
"""

from __future__ import annotations

import ctypes
import importlib.util
import platform
import re
from typing import Any, Final

from camera_count.core.enums import Protocol
from camera_count.usb.backend import EnumerationResult
from camera_count.usb.models import UsbDeviceInfo

_USB_IDS_RE: Final = re.compile(r"vid_([0-9a-f]{4})&pid_([0-9a-f]{4})", re.IGNORECASE)

#: A Windows instance id such as "6&1a2b3c&0&2" is assigned by the OS, not the
#: camera. Only an id without an ampersand is a device-supplied serial.
_INSTANCE_ID_RE: Final = re.compile(r"^[0-9a-z_.\-]+$", re.IGNORECASE)


class WpdBackend:
    """Windows Portable Devices, reached through COM with comtypes."""

    @property
    def name(self) -> str:
        return "wpd"

    # -- availability ---------------------------------------------------------

    def is_available(self) -> tuple[bool, str | None]:
        if platform.system() != "Windows":
            return False, "Windows Portable Devices is only available on Windows."
        if importlib.util.find_spec("comtypes") is None:
            return False, "comtypes is not installed; install the packaged release."
        try:
            self._manager()
        except Exception as exc:  # noqa: BLE001 - COM failures are reported, not raised
            return False, f"the Windows Portable Devices service could not be reached: {exc}"
        return True, None

    # -- COM plumbing ---------------------------------------------------------

    @staticmethod
    def _manager() -> Any:
        import comtypes  # noqa: PLC0415
        import comtypes.client  # noqa: PLC0415

        comtypes.CoInitialize()
        comtypes.client.GetModule("portabledeviceapi.dll")
        from comtypes.gen import PortableDeviceApiLib  # noqa: PLC0415

        return comtypes.client.CreateObject(
            PortableDeviceApiLib.PortableDeviceManager,
            interface=PortableDeviceApiLib.IPortableDeviceManager,
        )

    @staticmethod
    def _device_ids(manager: Any) -> list[str]:
        """List connected portable devices.

        comtypes exposes the WPD count parameter as in/out, so each call returns
        ``[buffer, count]``. The first call asks how many devices there are; the
        second fills a buffer of exactly that size.
        """
        count = _out_count(manager.GetDevices(None, 0))
        if count <= 0:
            return []
        buffer = (ctypes.c_wchar_p * count)()
        manager.GetDevices(buffer, count)
        return [value for value in buffer if value]

    @staticmethod
    def _device_string(manager: Any, accessor: str, device_id: str) -> str | None:
        """Read one device string, sizing the buffer from the device's own answer."""
        method = getattr(manager, accessor, None)
        if method is None:
            return None
        try:
            length = _out_count(method(device_id, None, 0))
            if length <= 0:
                return None
            buffer = ctypes.create_unicode_buffer(length)
            method(device_id, buffer, length)
        except Exception:  # noqa: BLE001 - a device that will not describe itself is fine
            return None
        return buffer.value.strip() or None

    # -- enumeration ----------------------------------------------------------

    def enumerate(self) -> EnumerationResult:
        available, reason = self.is_available()
        if not available:
            return EnumerationResult(backend=self.name, available=False, unavailable_reason=reason)

        warnings: list[str] = []
        devices: list[UsbDeviceInfo] = []
        try:
            manager = self._manager()
            manager.RefreshDeviceList()
            for device_id in self._device_ids(manager):
                devices.append(self._describe(manager, device_id))
        except Exception as exc:  # noqa: BLE001 - report, never crash detection
            return EnumerationResult(
                backend=self.name,
                available=True,
                devices=tuple(devices),
                warnings=(f"device enumeration stopped early: {exc}",),
            )

        return EnumerationResult(
            backend=self.name,
            available=True,
            devices=tuple(devices),
            warnings=tuple(warnings),
        )

    def _describe(self, manager: Any, device_id: str) -> UsbDeviceInfo:
        vendor_id, product_id = parse_usb_ids(device_id)
        return UsbDeviceInfo(
            vendor_id=vendor_id,
            product_id=product_id,
            address=device_id,
            backend=self.name,
            manufacturer=self._device_string(manager, "GetDeviceManufacturer", device_id),
            product=self._device_string(manager, "GetDeviceFriendlyName", device_id)
            or self._device_string(manager, "GetDeviceDescription", device_id),
            serial=parse_serial(device_id),
            interfaces=(),
            protocol=Protocol.MTP_WPD,
        )


def _out_count(returned: object) -> int:
    """Read the count out of a comtypes in/out return value.

    comtypes hands back either a bare integer or a list whose last element is
    the count, depending on how the type library declares the parameter. A
    value that is neither is treated as zero devices rather than being coerced.
    """
    if isinstance(returned, bool):
        return 0
    if isinstance(returned, int):
        return returned
    if isinstance(returned, (list, tuple)) and returned:
        tail = returned[-1]
        if isinstance(tail, int) and not isinstance(tail, bool):
            return tail
    return 0


def parse_usb_ids(device_id: str) -> tuple[int, int]:
    """Pull the vendor and product ids out of a WPD device id.

    Returns ``(0, 0)`` when the identifier does not carry them - some devices
    are reached over IP or Bluetooth rather than USB - rather than inventing a
    plausible pair.
    """
    match = _USB_IDS_RE.search(device_id)
    if match is None:
        return 0, 0
    return int(match.group(1), 16), int(match.group(2), 16)


def parse_serial(device_id: str) -> str | None:
    """Return the device-supplied serial from a WPD device id, if there is one.

    Windows substitutes a generated instance id such as ``6&1a2b3c&0&2`` for
    devices that report no serial number. That is a Windows artefact, not a
    camera serial, so it is reported as absent.
    """
    parts = device_id.split("#")
    if len(parts) < 3:
        return None
    candidate = parts[2].strip()
    if not candidate or "&" in candidate:
        return None
    if not _INSTANCE_ID_RE.match(candidate):
        return None
    return candidate
