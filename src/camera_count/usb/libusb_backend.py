"""Optional enumeration through libusb.

Windows reaches cameras through Windows Portable Devices, so this backend is
not installed by default and is not required. It exists for one case: a user
who has deliberately installed a WinUSB or libusb driver for their camera.
This program never installs, replaces, or removes a driver - install the extra
with ``uv pip install "camera-count-tool[winusb]"`` if you already run one.

Reading descriptors does not require claiming the device. Reading the string
descriptors does, so a device another process is holding still appears in the
list - with its names marked unavailable and ``claimed_by`` explaining who has
it. That is far more useful than a camera that silently does not exist.
"""

from __future__ import annotations

from typing import Any

from camera_count.core.enums import Protocol
from camera_count.usb.backend import EnumerationResult
from camera_count.usb.models import UsbDeviceInfo, UsbInterface


class LibusbBackend:
    """pyusb + libusb 1.0."""

    @property
    def name(self) -> str:
        return "libusb"

    # -- availability ---------------------------------------------------------

    def _load(self) -> tuple[Any, Any] | None:
        try:
            import usb.core  # noqa: PLC0415
            import usb.util  # noqa: PLC0415
        except ImportError:
            return None
        return usb.core, usb.util

    def _backend(self) -> Any:
        try:
            import libusb_package  # noqa: PLC0415
        except ImportError:
            return None
        try:
            return libusb_package.get_libusb1_backend()
        except Exception:  # noqa: BLE001 - a broken bundle must not crash detection
            return None

    def is_available(self) -> tuple[bool, str | None]:
        modules = self._load()
        if modules is None:
            return False, (
                "the optional libusb backend is not installed. This is normal: "
                "cameras are reached through Windows Portable Devices. Install "
                "camera-count-tool[winusb] only if you already run a WinUSB driver."
            )
        usb_core, _ = modules
        try:
            next(iter(usb_core.find(find_all=True, backend=self._backend())), None)
        except Exception as exc:  # noqa: BLE001 - libusb reports missing libraries here
            return False, f"libusb could not be initialised: {exc}"
        return True, None

    # -- enumeration ----------------------------------------------------------

    def enumerate(self) -> EnumerationResult:
        available, reason = self.is_available()
        if not available:
            return EnumerationResult(backend=self.name, available=False, unavailable_reason=reason)

        modules = self._load()
        assert modules is not None
        usb_core, usb_util = modules

        devices: list[UsbDeviceInfo] = []
        warnings: list[str] = []
        for device in usb_core.find(find_all=True, backend=self._backend()):
            try:
                info = self._describe(device, usb_util)
            except Exception as exc:  # noqa: BLE001 - one bad device must not hide the rest
                warnings.append(f"could not read a device descriptor: {exc}")
                continue
            if info is not None:
                devices.append(info)

        return EnumerationResult(
            backend=self.name,
            available=True,
            devices=tuple(devices),
            warnings=tuple(warnings),
        )

    def _describe(self, device: Any, usb_util: Any) -> UsbDeviceInfo | None:
        interfaces = tuple(self._interfaces(device))
        claimed_by = self._claimed_by(device, interfaces)
        manufacturer, product, serial = self._strings(device, usb_util)

        return UsbDeviceInfo(
            vendor_id=int(device.idVendor),
            product_id=int(device.idProduct),
            address=f"bus {getattr(device, 'bus', '?')} device {getattr(device, 'address', '?')}",
            backend=self.name,
            manufacturer=manufacturer,
            product=product,
            serial=serial,
            interfaces=interfaces,
            protocol=self._protocol(interfaces),
            claimed_by=claimed_by,
        )

    @staticmethod
    def _interfaces(device: Any) -> list[UsbInterface]:
        found: list[UsbInterface] = []
        for configuration in device:
            for interface in configuration:
                found.append(
                    UsbInterface(
                        number=int(interface.bInterfaceNumber),
                        interface_class=int(interface.bInterfaceClass),
                        subclass=int(interface.bInterfaceSubClass),
                        protocol=int(interface.bInterfaceProtocol),
                    )
                )
        return found

    @staticmethod
    def _protocol(interfaces: tuple[UsbInterface, ...]) -> Protocol:
        if any(interface.is_still_image for interface in interfaces):
            return Protocol.PTP_USB
        if interfaces and all(interface.is_mass_storage for interface in interfaces):
            return Protocol.MASS_STORAGE
        return Protocol.UNKNOWN

    def _claimed_by(self, device: Any, interfaces: tuple[UsbInterface, ...]) -> str | None:
        for interface in interfaces:
            try:
                if device.is_kernel_driver_active(interface.number):
                    return (
                        "another driver or program on this system. Close File "
                        "Explorer windows showing the camera and try again; see "
                        "docs/usb-debugging.md."
                    )
            except (NotImplementedError, AttributeError):
                return None
            except Exception:  # noqa: BLE001 - treat an unreadable state as unknown
                return None
        return None

    @staticmethod
    def _strings(device: Any, usb_util: Any) -> tuple[str | None, str | None, str | None]:
        def read(index: int) -> str | None:
            if not index:
                return None
            try:
                value = usb_util.get_string(device, index)
            except Exception:  # noqa: BLE001 - a busy device cannot answer; that is fine
                return None
            return str(value).strip() or None

        return (
            read(getattr(device, "iManufacturer", 0)),
            read(getattr(device, "iProduct", 0)),
            read(getattr(device, "iSerialNumber", 0)),
        )
