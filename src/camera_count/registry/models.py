"""Registry value objects.

A registry entry is the only thing in this program allowed to say "this field,
on this model, is the shutter count". Everything else defers to it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from camera_count.core.enums import (
    CountType,
    MethodType,
    Protocol,
    ValueSource,
    VerificationStatus,
)
from camera_count.core.sources import Citation, SourceRecord

_NORMALIZE_RE = re.compile(r"[\s_\-]+")


def normalize_name(text: str) -> str:
    """Fold a manufacturer or model string for comparison.

    Cameras report themselves inconsistently (``NIKON CORPORATION``,
    ``NIKON Z 6_2``), so comparison collapses runs of space, underscore and
    hyphen and case-folds. It never guesses beyond that: anything else must be
    listed as an alias.
    """
    return _NORMALIZE_RE.sub(" ", text).strip().casefold()


@dataclass(frozen=True, slots=True)
class ValueSpec:
    """Where the documented integer sits in an operation's answer."""

    source: ValueSource
    index: int = 0
    offset: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.index <= 4:
            raise ValueError(f"response parameter index out of range: {self.index}")
        if self.offset < 0:
            raise ValueError(f"data offset must not be negative: {self.offset}")


@dataclass(frozen=True, slots=True)
class RegisteredMethod:
    """One documented way to read one counter from one model."""

    source_id: str
    method_type: MethodType
    identifier: str
    count_type: CountType
    verification_status: VerificationStatus
    citation: Citation
    firmware_range: str | None = None
    value_spec: ValueSpec | None = None
    notes: str | None = None

    @property
    def is_camera_method(self) -> bool:
        """True for methods read from the camera rather than from a file."""
        return self.method_type in {
            MethodType.PTP_PROPERTY,
            MethodType.PTP_OPERATION,
            MethodType.SERVICE_INTERFACE,
        }

    @property
    def is_file_method(self) -> bool:
        return self.method_type is MethodType.MAKERNOTE_FIELD

    def numeric_identifier(self) -> int | None:
        """The identifier as an integer, when it is a code rather than a name."""
        text = self.identifier.strip()
        try:
            return int(text, 16) if text.lower().startswith("0x") else int(text)
        except ValueError:
            return None

    def is_trusted(self) -> bool:
        return self.verification_status in {
            VerificationStatus.DOCUMENTED,
            VerificationStatus.HARDWARE_VERIFIED,
        }


@dataclass(frozen=True, slots=True)
class CameraModel:
    """A model as recorded in the registry."""

    manufacturer: str
    model: str
    aliases: tuple[str, ...] = ()
    usb_vid: int | None = None
    usb_pid: int | None = None
    protocol: Protocol = Protocol.PTP_USB
    exact_count_available: bool = False
    methods: tuple[RegisteredMethod, ...] = ()
    limitations: tuple[str, ...] = ()
    notes: str | None = None

    def matches_name(self, reported_model: str) -> bool:
        candidate = normalize_name(reported_model)
        if not candidate:
            return False
        known = {normalize_name(self.model), *(normalize_name(a) for a in self.aliases)}
        return candidate in known

    def trusted_methods(self) -> tuple[RegisteredMethod, ...]:
        return tuple(method for method in self.methods if method.is_trusted())

    def source_records(self) -> tuple[SourceRecord, ...]:
        return tuple(
            SourceRecord(
                source_id=method.source_id,
                manufacturer=self.manufacturer,
                model=self.model,
                method_type=method.method_type,
                identifier=method.identifier,
                count_type=method.count_type,
                verification_status=method.verification_status,
                citation=method.citation,
                firmware_range=method.firmware_range,
            )
            for method in self.methods
        )


@dataclass(frozen=True, slots=True)
class VendorId:
    """A USB vendor id and the source that says whose it is."""

    id: int
    citation: Citation
    note: str | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.id <= 0xFFFF:
            raise ValueError(f"usb vendor id out of range: {self.id}")

    def display(self) -> str:
        return f"0x{self.id:04x}"


@dataclass(frozen=True, slots=True)
class ManufacturerEntry:
    """One YAML file: a manufacturer, its USB vendor ids, and its models."""

    manufacturer: str
    aliases: tuple[str, ...] = ()
    usb_vendor_ids: tuple[VendorId, ...] = ()
    models: tuple[CameraModel, ...] = ()
    notes: str | None = None

    @property
    def vendor_id_values(self) -> frozenset[int]:
        return frozenset(vendor.id for vendor in self.usb_vendor_ids)

    def owns_vendor_id(self, vid: int) -> bool:
        return vid in self.vendor_id_values

    def matches_manufacturer(self, reported: str) -> bool:
        candidate = normalize_name(reported)
        if not candidate:
            return False
        known = {normalize_name(self.manufacturer), *(normalize_name(a) for a in self.aliases)}
        if candidate in known:
            return True
        # A reported name that merely starts with the manufacturer name, such as
        # "NIKON CORPORATION" for "Nikon", is accepted; nothing looser is.
        return any(candidate.startswith(f"{name} ") for name in known)


def make_source_id(manufacturer: str, model: str, index: int) -> str:
    """Stable, human-readable id: ``nikon/nikon-z-6-2#0``."""
    return f"{_slug(manufacturer)}/{_slug(model)}#{index}"


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return slug or "unknown"
