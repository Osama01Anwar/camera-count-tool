"""Citations, source records, and the resolver every reading must pass through.

A reading may only exist if its ``source_id`` resolves to a registry entry whose
verification status is trusted. The registry package installs the resolver at
import time; :mod:`camera_count.core.models` never imports the registry
directly, which keeps the dependency one-way and makes the guard testable with a
stub resolver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from camera_count.core.enums import CitationKind, CountType, MethodType, VerificationStatus
from camera_count.core.errors import UnknownSourceError


@dataclass(frozen=True, slots=True)
class Citation:
    """Where a claim comes from.

    ``reference`` is either a URL or a ``repo/path:line`` source reference, for
    example ``libgphoto2/camlibs/ptp2/ptp.h:123``.
    """

    kind: CitationKind
    reference: str
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("citation reference must not be empty")
        if self.kind is CitationKind.URL and not self.reference.startswith(("http://", "https://")):
            raise ValueError(f"url citation must be an http(s) URL: {self.reference!r}")
        if self.kind is CitationKind.SOURCE_REF and ":" not in self.reference:
            raise ValueError(
                f"source_ref citation must look like 'repo/path:line': {self.reference!r}"
            )

    def display(self) -> str:
        return self.reference if self.note is None else f"{self.reference} ({self.note})"


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """One authoritative way to obtain one counter for one camera model."""

    source_id: str
    manufacturer: str
    model: str
    method_type: MethodType
    identifier: str
    count_type: CountType
    verification_status: VerificationStatus
    citation: Citation
    firmware_range: str | None = None

    def is_trusted(self) -> bool:
        from camera_count.core.enums import TRUSTED_STATUSES

        return self.verification_status in TRUSTED_STATUSES


@runtime_checkable
class SourceResolver(Protocol):
    """Anything that can turn a source id into a :class:`SourceRecord`."""

    def resolve(self, source_id: str) -> SourceRecord | None: ...


_resolver: SourceResolver | None = None


def set_source_resolver(resolver: SourceResolver | None) -> SourceResolver | None:
    """Install the resolver used by the reading factory. Returns the previous one."""
    global _resolver  # noqa: PLW0603
    previous = _resolver
    _resolver = resolver
    return previous


def get_source_resolver() -> SourceResolver | None:
    return _resolver


def resolve_source(source_id: str) -> SourceRecord:
    """Resolve ``source_id`` or raise.

    Raises:
        UnknownSourceError: no resolver installed, or the id is not in the registry.
    """
    if _resolver is None:
        raise UnknownSourceError(
            "no source resolver is installed; the camera registry must be loaded "
            "before any reading can be created"
        )
    record = _resolver.resolve(source_id)
    if record is None:
        raise UnknownSourceError(f"source id not found in the camera registry: {source_id!r}")
    return record
