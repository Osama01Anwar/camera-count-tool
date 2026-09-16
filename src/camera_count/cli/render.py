"""Turning results into text a buyer can read, and JSON a tool can parse.

The number and its source are the point. There are no colours conveying
meaning, no bars, no percentages, and nothing that could be mistaken for a
measurement the program did not make.
"""

from __future__ import annotations

from typing import Any

from camera_count.core.messages import (
    EXACT_COUNT_UNAVAILABLE,
    NOT_AVAILABLE,
    READ_ONLY_NOTICE,
    UNAVAILABLE_DISCLAIMER,
    VERIFIED_EXACT_COUNT,
)
from camera_count.core.models import (
    CameraIdentity,
    CounterSlot,
    NonAuthoritativeCounter,
    ShutterReading,
    Unavailable,
)
from camera_count.inspection import InspectionResult
from camera_count.usb.enumerate import DetectionReport
from camera_count.usb.models import UsbDeviceInfo

RULE = "-" * 68


def _label(count_type: str) -> str:
    return {
        "mechanical": "Mechanical shutter",
        "electronic": "Electronic shutter",
        "efc": "Electronic first curtain",
        "total_releases": "Total releases",
    }.get(count_type, count_type)


# --- detection ---------------------------------------------------------------


def device_lines(device: UsbDeviceInfo) -> list[str]:
    lines = [
        f"  USB id      : {device.usb_ids}",
        f"  Manufacturer: {device.display_manufacturer()}",
        f"  Product     : {device.display_product()}",
        f"  Serial      : {device.display_serial()}",
        f"  Protocol    : {device.protocol.value}",
        f"  Interfaces  : {device.describe_interfaces()}",
        f"  Backend     : {device.backend}",
    ]
    if device.claimed_by:
        lines.append(f"  In use by   : {device.claimed_by}")
    return lines


def render_detection(report: DetectionReport) -> str:
    lines: list[str] = ["Connected cameras", RULE]
    if not report.cameras:
        lines.append("No camera was found.")
        lines.append("")
        lines.append("Checks: is the camera switched on, connected with a data cable")
        lines.append("(not a charge-only cable), and set to PTP / PC Remote / MTP mode?")
    for index, camera in enumerate(report.cameras, start=1):
        lines.append(f"Camera {index}")
        lines.extend(device_lines(camera))
        lines.append("")

    others = [d for d in report.devices if d not in report.cameras]
    if others:
        lines.append(f"Other portable devices seen: {len(others)} (not cameras)")

    for backend, reason in report.unavailable_backends:
        lines.append(f"Backend {backend}: {reason}")
    for warning in report.warnings:
        lines.append(f"Note: {warning}")
    return "\n".join(lines).rstrip()


def detection_json(report: DetectionReport) -> dict[str, Any]:
    return {
        "cameras": [_device_json(camera) for camera in report.cameras],
        "other_devices": [
            _device_json(device) for device in report.devices if device not in report.cameras
        ],
        "backends_unavailable": [
            {"backend": backend, "reason": reason}
            for backend, reason in report.unavailable_backends
        ],
        "warnings": list(report.warnings),
    }


def _device_json(device: UsbDeviceInfo) -> dict[str, Any]:
    return {
        "usb_vendor_id": f"0x{device.vendor_id:04x}",
        "usb_product_id": f"0x{device.product_id:04x}",
        "manufacturer": device.manufacturer,
        "product": device.product,
        "serial": device.serial,
        "protocol": device.protocol.value,
        "backend": device.backend,
        "address": device.address,
        "claimed_by": device.claimed_by,
        "interfaces": [
            {
                "number": interface.number,
                "class": f"0x{interface.interface_class:02x}",
                "subclass": f"0x{interface.subclass:02x}",
                "protocol": f"0x{interface.protocol:02x}",
                "still_image": interface.is_still_image,
            }
            for interface in device.interfaces
        ],
    }


# --- identity and counts -----------------------------------------------------


def render_identity(identity: CameraIdentity) -> str:
    return "\n".join(
        [
            "Camera",
            RULE,
            f"  Manufacturer: {identity.display_manufacturer()}",
            f"  Model       : {identity.display_model()}",
            f"  Serial      : {identity.display_serial()}",
            f"  Firmware    : {identity.display_firmware()}",
            f"  Protocol    : {identity.protocol.value}",
        ]
    )


def render_counter(slot: CounterSlot, *, show_reason: bool = True) -> list[str]:
    label = _label(slot.count_type.value)
    result = slot.result
    if isinstance(result, ShutterReading):
        return [
            f"  {label:<26}: {result.value}",
            f"  {'':26}  source: {result.source.method_type.value} {result.source.identifier}",
            f"  {'':26}  status: {result.source.verification_status.value}",
            f"  {'':26}  cited : {result.source.citation.display()}",
        ]
    lines = [f"  {label:<26}: {NOT_AVAILABLE}"]
    if show_reason:
        lines.append(f"  {'':26}  {result.reason}")
    return lines


def render_inspection(result: InspectionResult, *, show_counts: bool = True) -> str:
    lines = [render_identity(result.identity), ""]

    if result.failure is not None:
        lines.extend(
            [
                EXACT_COUNT_UNAVAILABLE,
                RULE,
                f"  {result.failure.message}",
                f"  {result.failure.reason}",
                f"  {UNAVAILABLE_DISCLAIMER}",
            ]
        )
        return "\n".join(lines)

    if not show_counts:
        return "\n".join(lines).rstrip()

    lines.append(result.headline)
    lines.append(RULE)
    for slot in result.counters:
        lines.extend(render_counter(slot))
    if not result.has_exact_count:
        lines.append(f"  {UNAVAILABLE_DISCLAIMER}")

    if result.model and result.model.limitations:
        lines.append("")
        lines.append("Limitations")
        lines.extend(f"  - {item}" for item in result.model.limitations)

    lines.append("")
    lines.append(f"Adapter: {result.adapter}   Transactions: {len(result.log)}")
    lines.append(READ_ONLY_NOTICE)
    return "\n".join(lines)


def counter_json(slot: CounterSlot) -> dict[str, Any]:
    result = slot.result
    if isinstance(result, ShutterReading):
        return {
            "counter": slot.count_type.value,
            "available": True,
            "value": result.value,
            "source_id": result.source_id,
            "method": result.source.method_type.value,
            "identifier": result.source.identifier,
            "verification_status": result.source.verification_status.value,
            "citation": result.source.citation.reference,
            "transaction": result.transaction_ref,
        }
    return {
        "counter": slot.count_type.value,
        "available": False,
        "value": None,
        "message": result.message,
        "reason": result.reason,
        "disclaimer": UNAVAILABLE_DISCLAIMER,
    }


def inspection_json(result: InspectionResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "headline": result.headline,
        "exact_count_found": result.has_exact_count,
        "camera": {
            "manufacturer": result.identity.manufacturer,
            "model": result.identity.model,
            "serial": result.identity.serial,
            "firmware": result.identity.firmware,
            "protocol": result.identity.protocol.value,
        },
        "registry_model": result.model.model if result.model else None,
        "adapter": result.adapter,
        "counters": [counter_json(slot) for slot in result.counters],
        "transaction_count": len(result.log),
    }
    if result.failure is not None:
        payload["failure"] = {
            "message": result.failure.message,
            "reason": result.failure.reason,
            "disclaimer": UNAVAILABLE_DISCLAIMER,
        }
    if result.device is not None:
        payload["device"] = _device_json(result.device)
    return payload


def render_non_authoritative(counters: tuple[NonAuthoritativeCounter, ...]) -> list[str]:
    """Render counters that exist but may never fill a shutter-count slot."""
    if not counters:
        return []
    from camera_count.core.messages import IMAGE_COUNTER_NOTICE  # noqa: PLC0415

    lines = ["", IMAGE_COUNTER_NOTICE]
    lines.extend(
        f"  {counter.label}: {counter.value}  (from {counter.origin})" for counter in counters
    )
    return lines


# --- image files -------------------------------------------------------------


def render_file_analysis(analysis: Any) -> str:
    """Render one analysed file: what it is, whether it is original, what it proves."""
    lines = [
        f"File: {analysis.path.name}",
        RULE,
        f"  Full path   : {analysis.path}",
        f"  Size        : {analysis.size_bytes} bytes",
        f"  SHA-256     : {analysis.sha256 or NOT_AVAILABLE}",
        f"  Format      : {analysis.file_type or NOT_AVAILABLE}",
        f"  Make        : {analysis.make or NOT_AVAILABLE}",
        f"  Model       : {analysis.model or NOT_AVAILABLE}",
        f"  Captured    : {analysis.display_capture_date()}",
        "",
    ]

    if analysis.originality is not None:
        verdict = "original camera file" if analysis.is_original else "NOT AN ORIGINAL CAMERA FILE"
        lines.append(f"Originality: {verdict}")
        lines.extend(f"  {check.describe()}" for check in analysis.originality.checks)
        lines.append("")

    lines.append(VERIFIED_EXACT_COUNT if analysis.has_exact_count else EXACT_COUNT_UNAVAILABLE)
    # When one thing stopped the whole file, say it once here rather than
    # repeating it under every counter.
    blocking = getattr(analysis, "blocking_failure", None)
    if blocking is not None:
        lines.append(f"  {blocking.message}")
        lines.append(f"  {blocking.reason}")
    for slot in analysis.counter_slots():
        lines.extend(render_counter(slot, show_reason=blocking is None))
    if not analysis.has_exact_count:
        lines.append(f"  {UNAVAILABLE_DISCLAIMER}")

    lines.extend(render_non_authoritative(analysis.non_authoritative))
    return "\n".join(lines)


def file_analysis_json(analysis: Any) -> dict[str, Any]:
    return {
        "file": str(analysis.path),
        "name": analysis.path.name,
        "size_bytes": analysis.size_bytes,
        "sha256": analysis.sha256,
        "format": analysis.file_type,
        "make": analysis.make,
        "model": analysis.model,
        "capture_date": analysis.capture_date,
        "is_original": analysis.is_original,
        "originality_checks": [
            {"name": check.name, "passed": check.passed, "detail": check.detail}
            for check in (analysis.originality.checks if analysis.originality else ())
        ],
        "counters": [counter_json(slot) for slot in analysis.counter_slots()],
        "non_authoritative_counters": [
            {"label": counter.label, "value": counter.value, "origin": counter.origin}
            for counter in analysis.non_authoritative
        ],
    }


def render_analyses(analyses: Any, *, notice: str | None = None) -> str:
    blocks = [render_file_analysis(analysis) for analysis in analyses]
    if notice:
        blocks.append(notice)
    return "\n\n".join(blocks)


def render_unavailable(result: Unavailable) -> str:
    return "\n".join(
        [
            EXACT_COUNT_UNAVAILABLE,
            RULE,
            f"  {result.message}",
            f"  {result.reason}",
            f"  {UNAVAILABLE_DISCLAIMER}",
        ]
    )


HEADLINES = {True: VERIFIED_EXACT_COUNT, False: EXACT_COUNT_UNAVAILABLE}
