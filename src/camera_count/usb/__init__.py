"""USB enumeration: one device model, one backend per platform."""

from __future__ import annotations

from camera_count.usb.backend import EnumerationBackend, EnumerationResult
from camera_count.usb.enumerate import (
    DetectionReport,
    default_backends,
    detect,
    is_camera_candidate,
)
from camera_count.usb.libusb_backend import LibusbBackend
from camera_count.usb.models import UsbDeviceInfo, UsbInterface
from camera_count.usb.wpd_backend import WpdBackend

__all__ = [
    "DetectionReport",
    "EnumerationBackend",
    "EnumerationResult",
    "LibusbBackend",
    "UsbDeviceInfo",
    "UsbInterface",
    "WpdBackend",
    "default_backends",
    "detect",
    "is_camera_candidate",
]
