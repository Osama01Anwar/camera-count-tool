"""Analysing image files: hash, identify, check, and read documented counters."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from camera_count.core.errors import ToolNotFoundError
from camera_count.core.messages import (
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    HISTORICAL_COUNTS_NOTICE,
    NOT_AVAILABLE,
    REASON_NO_EXIFTOOL,
)
from camera_count.core.models import (
    CountResult,
    NonAuthoritativeCounter,
    ShutterReading,
    Unavailable,
    build_counter_slots,
)
from camera_count.metadata.exiftool import read_metadata
from camera_count.metadata.fields import counters_from_tags, non_authoritative_counters
from camera_count.metadata.originality import OriginalityVerdict, assess_originality, find_tag
from camera_count.registry import CameraRegistry, load_default_registry
from camera_count.registry.models import CameraModel

HASH_CHUNK_BYTES: Final = 1024 * 1024

CAPTURE_DATE_TAGS: Final[tuple[str, ...]] = (
    "DateTimeOriginal",
    "CreateDate",
    "SubSecDateTimeOriginal",
    "FileModifyDate",
)


def sha256_of(path: Path) -> str:
    """Hash a file without loading it into memory. Opened read-only."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class FileAnalysis:
    """What one file turned out to be, and what it could prove."""

    path: Path
    size_bytes: int
    sha256: str
    file_type: str | None = None
    make: str | None = None
    model: str | None = None
    capture_date: str | None = None
    registry_model: CameraModel | None = None
    originality: OriginalityVerdict | None = None
    results: tuple[CountResult, ...] = ()
    non_authoritative: tuple[NonAuthoritativeCounter, ...] = ()
    tags: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_original(self) -> bool:
        return self.originality is not None and self.originality.is_original

    @property
    def exact_reading(self) -> ShutterReading | None:
        for result in self.results:
            if isinstance(result, ShutterReading):
                return result
        return None

    @property
    def has_exact_count(self) -> bool:
        return self.exact_reading is not None

    def display_capture_date(self) -> str:
        return self.capture_date or NOT_AVAILABLE

    @property
    def blocking_failure(self) -> Unavailable | None:
        """A result that applies to the whole file rather than to one counter."""
        for result in self.results:
            if isinstance(result, Unavailable) and result.count_type is None:
                return result
        return None

    def counter_slots(self) -> tuple[Any, ...]:
        """Counter slots, each carrying the reason that actually applies.

        When something stopped the whole file - it is not an original, or
        ExifTool is missing - every empty slot says so, rather than falling back
        to a generic "not in the registry" that would misdescribe the problem.
        """
        blocking = self.blocking_failure
        if blocking is None:
            return build_counter_slots(self.results)
        return build_counter_slots(self.results, absent_reason=blocking.reason)


def _string_tag(tags: dict[str, Any], name: str) -> str | None:
    found = find_tag(tags, name)
    if found is None:
        return None
    text = str(found[1]).strip()
    return text or None


def _capture_date(tags: dict[str, Any]) -> str | None:
    for name in CAPTURE_DATE_TAGS:
        value = _string_tag(tags, name)
        if value:
            return value
    return None


def analyze_files(
    paths: Sequence[Path], *, registry: CameraRegistry | None = None
) -> tuple[FileAnalysis, ...]:
    """Analyse each file. A missing ExifTool is reported, never worked around."""
    if not paths:
        return ()

    registry = registry or load_default_registry()

    try:
        documents = read_metadata(list(paths))
    except ToolNotFoundError:
        return tuple(
            FileAnalysis(
                path=Path(path),
                size_bytes=Path(path).stat().st_size if Path(path).is_file() else 0,
                sha256=sha256_of(Path(path)) if Path(path).is_file() else "",
                results=(
                    Unavailable(
                        message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                        reason=REASON_NO_EXIFTOOL,
                    ),
                ),
            )
            for path in paths
        )

    by_source: dict[str, dict[str, Any]] = {}
    for document in documents:
        source = str(document.get("SourceFile", ""))
        if source:
            by_source[Path(source).resolve().as_posix().casefold()] = document

    analyses: list[FileAnalysis] = []
    for path in paths:
        resolved = Path(path).expanduser().resolve(strict=False)
        tags = by_source.get(resolved.as_posix().casefold(), {})
        analyses.append(_analyze_one(resolved, tags, registry))
    return tuple(analyses)


def _analyze_one(path: Path, tags: dict[str, Any], registry: CameraRegistry) -> FileAnalysis:
    verdict = assess_originality(tags) if tags else None
    make = _string_tag(tags, "Make")
    model_name = _string_tag(tags, "Model")
    registry_model = registry.find_model(make, model_name)

    if verdict is None:
        results: tuple[CountResult, ...] = (
            Unavailable(
                message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                reason="No metadata could be read from this file.",
            ),
        )
    else:
        results = counters_from_tags(registry_model, tags, verdict)

    return FileAnalysis(
        path=path,
        size_bytes=path.stat().st_size if path.is_file() else 0,
        sha256=sha256_of(path) if path.is_file() else "",
        file_type=_string_tag(tags, "FileType"),
        make=make,
        model=model_name,
        capture_date=_capture_date(tags),
        registry_model=registry_model,
        originality=verdict,
        results=results,
        non_authoritative=non_authoritative_counters(tags),
        tags=tags,
    )


def historical_notice(analyses: Sequence[FileAnalysis]) -> str | None:
    """The reminder that a file's count is history, not the current count."""
    if any(analysis.has_exact_count for analysis in analyses):
        return HISTORICAL_COUNTS_NOTICE
    return None
