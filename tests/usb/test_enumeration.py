"""Device model behaviour, WPD identifier parsing, and detection."""

from __future__ import annotations

import pytest

from camera_count.core.enums import Protocol
from camera_count.core.messages import NOT_AVAILABLE
from camera_count.usb.backend import EnumerationResult
from camera_count.usb.enumerate import detect, is_camera_candidate
from camera_count.usb.models import UsbDeviceInfo, UsbInterface
from camera_count.usb.wpd_backend import parse_serial, parse_usb_ids

STILL_IMAGE = UsbInterface(number=0, interface_class=0x06, subclass=0x01, protocol=0x01)
MASS_STORAGE = UsbInterface(number=0, interface_class=0x08, subclass=0x06, protocol=0x50)
VENDOR_SPECIFIC = UsbInterface(number=0, interface_class=0xFF, subclass=0x00, protocol=0x00)


class StubBackend:
    def __init__(self, result: EnumerationResult) -> None:
        self._result = result

    @property
    def name(self) -> str:
        return self._result.backend

    def is_available(self) -> tuple[bool, str | None]:
        return self._result.available, self._result.unavailable_reason

    def enumerate(self) -> EnumerationResult:
        return self._result


def device(**kwargs: object) -> UsbDeviceInfo:
    defaults: dict[str, object] = {
        "vendor_id": 0x04B0,
        "product_id": 0x0428,
        "address": "bus 1 device 2",
        "backend": "stub",
    }
    return UsbDeviceInfo(**{**defaults, **kwargs})  # type: ignore[arg-type]


# --- interface classification ------------------------------------------------


def test_still_image_interface_is_recognised() -> None:
    assert STILL_IMAGE.is_still_image
    assert not MASS_STORAGE.is_still_image
    assert not VENDOR_SPECIFIC.is_still_image


def test_mass_storage_only_device_is_flagged() -> None:
    camera = device(interfaces=(MASS_STORAGE,))

    assert camera.is_mass_storage_only
    assert not camera.is_still_image_device


def test_unknown_fields_display_as_not_available() -> None:
    camera = device()

    assert camera.display_manufacturer() == NOT_AVAILABLE
    assert camera.display_product() == NOT_AVAILABLE
    assert camera.display_serial() == NOT_AVAILABLE
    assert camera.describe_interfaces() == NOT_AVAILABLE


def test_usb_ids_are_formatted_for_display() -> None:
    assert device().usb_ids == "04b0:0428"


# --- WPD identifier parsing --------------------------------------------------


def test_usb_ids_are_read_from_the_wpd_identifier() -> None:
    identifier = (
        r"\\?\usb#vid_04b0&pid_0428#0123456789#"
        r"{6ac27878-a6fa-4155-ba85-f98f491d4f33}"
    )

    assert parse_usb_ids(identifier) == (0x04B0, 0x0428)


def test_non_usb_identifier_yields_no_ids_rather_than_a_guess() -> None:
    assert parse_usb_ids(r"\\?\wpdbusenumroot#umb#2&37c186b&0&storage") == (0, 0)


def test_device_supplied_serial_is_returned() -> None:
    identifier = r"\\?\usb#vid_04b0&pid_0428#0123456789#{guid}"

    assert parse_serial(identifier) == "0123456789"


def test_windows_generated_instance_id_is_not_treated_as_a_serial() -> None:
    identifier = r"\\?\usb#vid_04b0&pid_0428#6&1a2b3c&0&2#{guid}"

    assert parse_serial(identifier) is None


def test_identifier_without_an_instance_section_has_no_serial() -> None:
    assert parse_serial(r"\\?\usb#vid_04b0&pid_0428") is None


# --- candidate selection -----------------------------------------------------

KNOWN_VENDORS = frozenset({0x04B0, 0x04A9})


def test_still_image_class_makes_a_candidate_whatever_the_vendor() -> None:
    unknown_vendor = device(vendor_id=0xABCD, interfaces=(STILL_IMAGE,))

    assert is_camera_candidate(unknown_vendor, KNOWN_VENDORS)


def test_known_camera_vendor_makes_a_candidate() -> None:
    assert is_camera_candidate(device(protocol=Protocol.MTP_WPD), KNOWN_VENDORS)


def test_a_phone_on_the_same_bus_is_not_a_candidate() -> None:
    phone = device(vendor_id=0x04E8, product_id=0x6860, protocol=Protocol.MTP_WPD)

    assert not is_camera_candidate(phone, KNOWN_VENDORS)


# --- detection ---------------------------------------------------------------


def test_detection_merges_backends_and_deduplicates() -> None:
    same = device(interfaces=(STILL_IMAGE,))
    backends = (
        StubBackend(EnumerationResult(backend="a", available=True, devices=(same,))),
        StubBackend(EnumerationResult(backend="b", available=True, devices=(same,))),
    )

    report = detect(backends=backends, known_vendor_ids=KNOWN_VENDORS)

    assert len(report.devices) == 1
    assert report.has_camera


def test_detection_reports_why_a_backend_could_not_run() -> None:
    backends = (
        StubBackend(
            EnumerationResult(
                backend="libusb",
                available=False,
                unavailable_reason="pyusb is not installed.",
            )
        ),
    )

    report = detect(backends=backends, known_vendor_ids=KNOWN_VENDORS)

    assert not report.has_camera
    assert report.unavailable_backends == (("libusb", "pyusb is not installed."),)


def test_detection_surfaces_a_blocked_camera_instead_of_hiding_it() -> None:
    blocked = device(interfaces=(STILL_IMAGE,), claimed_by="another program")
    backends = (StubBackend(EnumerationResult(backend="a", available=True, devices=(blocked,))),)

    report = detect(backends=backends, known_vendor_ids=KNOWN_VENDORS)

    assert report.has_camera
    assert report.blocked_cameras == (blocked,)


def test_detection_surfaces_mass_storage_mode() -> None:
    card_reader_mode = device(interfaces=(MASS_STORAGE,))
    backends = (
        StubBackend(EnumerationResult(backend="a", available=True, devices=(card_reader_mode,))),
    )

    report = detect(backends=backends, known_vendor_ids=KNOWN_VENDORS)

    assert report.mass_storage_cameras == (card_reader_mode,)


@pytest.mark.parametrize("backend_name", ["libusb", "wpd"])
def test_real_backends_report_availability_without_raising(backend_name: str) -> None:
    """Whatever this machine has, asking must never blow up."""
    from camera_count.usb import LibusbBackend, WpdBackend

    backend = LibusbBackend() if backend_name == "libusb" else WpdBackend()

    available, reason = backend.is_available()

    assert isinstance(available, bool)
    assert available or reason
