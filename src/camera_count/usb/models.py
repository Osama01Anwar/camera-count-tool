"""What an enumerated USB device looks like, whichever backend found it."""

from __future__ import annotations

from dataclasses import dataclass

from camera_count.core.enums import Protocol
from camera_count.core.messages import NOT_AVAILABLE
from camera_count.ptp.constants import (
    USB_CLASS_STILL_IMAGE,
    USB_PROTOCOL_PTP,
    USB_SUBCLASS_STILL_IMAGE,
)

#: USB Mass Storage class - a camera in this mode offers no protocol access.
USB_CLASS_MASS_STORAGE = 0x08


@dataclass(frozen=True, slots=True)
class UsbInterface:
    """One USB interface descriptor, as reported by the device."""

    number: int
    interface_class: int
    subclass: int
    protocol: int

    @property
    def is_still_image(self) -> bool:
        """True for the USB Still Image class used by PTP (6/1/1)."""
        return (
            self.interface_class == USB_CLASS_STILL_IMAGE
            and self.subclass == USB_SUBCLASS_STILL_IMAGE
            and self.protocol == USB_PROTOCOL_PTP
        )

    @property
    def is_mass_storage(self) -> bool:
        return self.interface_class == USB_CLASS_MASS_STORAGE

    def describe(self) -> str:
        return (
            f"interface {self.number}: class 0x{self.interface_class:02X} "
            f"subclass 0x{self.subclass:02X} protocol 0x{self.protocol:02X}"
        )


@dataclass(frozen=True, slots=True)
class UsbDeviceInfo:
    """A device as enumerated. Fields the backend could not read stay None."""

    vendor_id: int
    product_id: int
    address: str
    backend: str
    manufacturer: str | None = None
    product: str | None = None
    serial: str | None = None
    interfaces: tuple[UsbInterface, ...] = ()
    protocol: Protocol = Protocol.UNKNOWN
    claimed_by: str | None = None

    @property
    def usb_ids(self) -> str:
        return f"{self.vendor_id:04x}:{self.product_id:04x}"

    @property
    def is_still_image_device(self) -> bool:
        return any(interface.is_still_image for interface in self.interfaces)

    @property
    def is_mass_storage_only(self) -> bool:
        return bool(self.interfaces) and all(
            interface.is_mass_storage for interface in self.interfaces
        )

    @property
    def is_accessible(self) -> bool:
        return self.claimed_by is None

    def display_manufacturer(self) -> str:
        return self.manufacturer or NOT_AVAILABLE

    def display_product(self) -> str:
        return self.product or NOT_AVAILABLE

    def display_serial(self) -> str:
        return self.serial or NOT_AVAILABLE

    def describe_interfaces(self) -> str:
        if not self.interfaces:
            return NOT_AVAILABLE
        return "; ".join(interface.describe() for interface in self.interfaces)
