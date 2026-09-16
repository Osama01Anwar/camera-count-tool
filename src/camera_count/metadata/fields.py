"""Pulling counters out of metadata - only the fields the registry names.

The registry identifier for a MakerNotes method is ``Group:Tag`` exactly as
ExifTool reports it with ``-G1``. Matching is exact. A tag with a similar name
in a different group is a different tag, and this program does not go looking
for near misses.
"""

from __future__ import annotations

from typing import Any, Final

from camera_count.core.messages import (
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    NOT_AN_ORIGINAL_CAMERA_FILE,
    REASON_FIELD_ABSENT,
    REASON_NO_REGISTRY_ENTRY,
    REASON_NOT_ORIGINAL,
)
from camera_count.core.models import (
    CountResult,
    NonAuthoritativeCounter,
    ShutterReading,
    Unavailable,
)
from camera_count.metadata.originality import OriginalityVerdict, tag_name
from camera_count.registry.models import CameraModel

#: Counters that exist in camera metadata but are not shutter counts. They are
#: shown under the image-counter notice and never in a counter slot.
NON_AUTHORITATIVE_TAGS: Final[tuple[str, ...]] = (
    "FileIndex",
    "FileNumber",
    "ImageNumber",
    "FrameNumber",
    "SequenceNumber",
    "ImageCount",
    "DirectoryIndex",
    "ShutterCurtainSync",
    "ExposureSequenceNumber",
)

REASON_NO_FILE_METHOD: Final = (
    "No MakerNotes field is documented as the shutter count for this model."
)


def lookup_field(tags: dict[str, Any], identifier: str) -> tuple[str, Any] | None:
    """Find ``Group:Tag`` exactly, ignoring only letter case."""
    wanted = identifier.strip().casefold()
    for key, value in tags.items():
        if key.casefold() == wanted:
            return key, value
    return None


def parse_counter_value(value: Any) -> int | None:
    """Accept only a plain non-negative integer. Anything else is not a count."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def counters_from_tags(
    model: CameraModel | None,
    tags: dict[str, Any],
    verdict: OriginalityVerdict,
) -> tuple[CountResult, ...]:
    """Read every documented MakerNotes counter for this model."""
    if not verdict.is_original:
        return (
            Unavailable(
                message=NOT_AN_ORIGINAL_CAMERA_FILE,
                reason=f"{REASON_NOT_ORIGINAL} {verdict.reason}",
            ),
        )

    if model is None:
        return (
            Unavailable(message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason=REASON_NO_REGISTRY_ENTRY),
        )

    file_methods = [method for method in model.trusted_methods() if method.is_file_method]
    if not file_methods:
        return (
            Unavailable(message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason=REASON_NO_FILE_METHOD),
        )

    results: list[CountResult] = []
    for method in file_methods:
        found = lookup_field(tags, method.identifier)
        if found is None:
            results.append(
                Unavailable(
                    message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                    reason=f"{REASON_FIELD_ABSENT} ({method.identifier})",
                    count_type=method.count_type,
                )
            )
            continue

        key, raw = found
        value = parse_counter_value(raw)
        if value is None:
            results.append(
                Unavailable(
                    message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
                    reason=(f"{key} holds {raw!r}, which is not a plain counter integer."),
                    count_type=method.count_type,
                )
            )
            continue

        results.append(
            ShutterReading.from_source(value=value, source_id=method.source_id, transaction_ref=key)
        )
    return tuple(results)


def non_authoritative_counters(tags: dict[str, Any]) -> tuple[NonAuthoritativeCounter, ...]:
    """Collect counters that are present but are not shutter counts."""
    found: list[NonAuthoritativeCounter] = []
    for key, value in tags.items():
        name = tag_name(key)
        if name in NON_AUTHORITATIVE_TAGS:
            found.append(NonAuthoritativeCounter(label=name, value=str(value), origin=key))
    return tuple(found)
