"""Enumerations shared across the whole application.

These live in their own module so that both the source registry and the result
models can import them without a circular dependency.
"""

from __future__ import annotations

from enum import StrEnum


class CountType(StrEnum):
    """A counter kind, as defined by the camera manufacturer.

    Counters are never merged and never combined arithmetically. Each value is
    reported on its own, exactly as the camera or the manufacturer-documented
    metadata field reports it.
    """

    MECHANICAL = "mechanical"
    ELECTRONIC = "electronic"
    EFC = "efc"
    TOTAL_RELEASES = "total_releases"


class MethodType(StrEnum):
    """How an exact count is obtained for a given camera model."""

    PTP_PROPERTY = "ptp_property"
    PTP_OPERATION = "ptp_operation"
    MAKERNOTE_FIELD = "makernote_field"
    SERVICE_INTERFACE = "service_interface"


class VerificationStatus(StrEnum):
    """How far a registry method has been verified.

    Only DOCUMENTED and HARDWARE_VERIFIED may ever produce a displayed count.
    """

    UNVERIFIED = "unverified"
    DOCUMENTED = "documented"
    HARDWARE_VERIFIED = "hardware_verified"


#: Statuses that permit a reading to be constructed and displayed.
TRUSTED_STATUSES: frozenset[VerificationStatus] = frozenset(
    {VerificationStatus.DOCUMENTED, VerificationStatus.HARDWARE_VERIFIED}
)


class CitationKind(StrEnum):
    """Where a citation points."""

    URL = "url"
    SOURCE_REF = "source_ref"


class Protocol(StrEnum):
    """Transport/protocol a device speaks, as observed - never assumed."""

    PTP_USB = "ptp_usb"
    MTP_WPD = "mtp_wpd"
    MASS_STORAGE = "mass_storage"
    UNKNOWN = "unknown"
