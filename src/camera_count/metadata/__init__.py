"""Reading metadata from original camera files."""

from __future__ import annotations

from camera_count.metadata.analyze import (
    FileAnalysis,
    analyze_files,
    historical_notice,
    sha256_of,
)
from camera_count.metadata.exiftool import (
    EXIFTOOL_ENV,
    ExifToolInfo,
    build_command,
    exiftool_info,
    find_exiftool,
    find_perl,
    read_metadata,
)
from camera_count.metadata.fields import (
    counters_from_tags,
    lookup_field,
    non_authoritative_counters,
    parse_counter_value,
)
from camera_count.metadata.originality import (
    Check,
    OriginalityVerdict,
    assess_originality,
    has_maker_notes,
)

__all__ = [
    "EXIFTOOL_ENV",
    "Check",
    "ExifToolInfo",
    "FileAnalysis",
    "OriginalityVerdict",
    "analyze_files",
    "assess_originality",
    "build_command",
    "counters_from_tags",
    "exiftool_info",
    "find_exiftool",
    "find_perl",
    "has_maker_notes",
    "historical_notice",
    "lookup_field",
    "non_authoritative_counters",
    "parse_counter_value",
    "read_metadata",
    "sha256_of",
]
