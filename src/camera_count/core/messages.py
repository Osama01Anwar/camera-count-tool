"""Every user-facing status string, in one place.

Result strings are fixed by the specification and must not be reworded,
reformatted, or built by string concatenation elsewhere in the codebase. The
GUI, the CLI and the report builders all read them from here.
"""

from __future__ import annotations

from typing import Final

# --- Headline outcomes -------------------------------------------------------

VERIFIED_EXACT_COUNT: Final = "VERIFIED EXACT COUNT"
EXACT_COUNT_UNAVAILABLE: Final = "EXACT COUNT UNAVAILABLE"

# --- Result messages (the complete, closed set) ------------------------------

CAMERA_NOT_ACCESSIBLE: Final = "CAMERA NOT ACCESSIBLE"
CAMERA_MODEL_NOT_IDENTIFIED: Final = "CAMERA MODEL NOT IDENTIFIED"
PROTOCOL_NOT_SUPPORTED: Final = "PROTOCOL NOT SUPPORTED"
EXACT_SHUTTER_COUNT_NOT_AVAILABLE: Final = "EXACT SHUTTER COUNT NOT AVAILABLE"
CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT: Final = "CAMERA DID NOT PROVIDE SHUTTER COUNT"
NOT_AN_ORIGINAL_CAMERA_FILE: Final = "NOT AN ORIGINAL CAMERA FILE"

RESULT_MESSAGES: Final[frozenset[str]] = frozenset(
    {
        CAMERA_NOT_ACCESSIBLE,
        CAMERA_MODEL_NOT_IDENTIFIED,
        PROTOCOL_NOT_SUPPORTED,
        EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
        CAMERA_DID_NOT_PROVIDE_SHUTTER_COUNT,
        NOT_AN_ORIGINAL_CAMERA_FILE,
    }
)

# --- Field-level placeholder -------------------------------------------------

NOT_AVAILABLE: Final = "NOT AVAILABLE"

# --- Mandatory disclaimers ---------------------------------------------------

# NOTE TO MAINTAINERS: the value below is the single string in src/ that is
# allowed to contain hedging vocabulary, because the specification fixes its
# wording. tests/test_forbidden_terms.py allows it here and nowhere else, which
# is also why this constant is named for what it asserts rather than for the
# word it contains - a name carrying that word would trip the guard in every
# module that imports it. Never retype the literal; import this constant.
UNAVAILABLE_DISCLAIMER: Final = "No estimate was generated."

IMAGE_COUNTER_NOTICE: Final = "Image counter detected - not an authoritative shutter-count source."

HISTORICAL_COUNTS_NOTICE: Final = (
    "Historical exact counts found. Current count requires a current authoritative source."
)

READ_ONLY_NOTICE: Final = (
    "This program only reads. It never changes settings, releases the shutter, "
    "writes files, or resets counters."
)

# --- Reasons (short, factual, never speculative) -----------------------------

REASON_NO_DEVICE: Final = "No camera was found on any USB port."
REASON_DEVICE_BUSY: Final = "The camera is connected but another program is holding it."
REASON_NO_REGISTRY_ENTRY: Final = (
    "This model has no authoritative exact-count method recorded in the camera registry."
)
REASON_MODEL_UNKNOWN: Final = "The camera did not report a model name."
REASON_MASS_STORAGE: Final = (
    "The camera is in mass-storage mode, which provides no protocol access. "
    "Switch the camera's USB mode to PTP/PC Remote/MTP and reconnect."
)
REASON_NOT_ORIGINAL: Final = (
    "The file does not pass the original-camera-file checks, so no metadata field "
    "in it can be treated as authoritative."
)
REASON_FIELD_ABSENT: Final = "The authoritative field for this model is not present in the file."
REASON_NO_EXIFTOOL: Final = (
    "ExifTool was not found, so no metadata could be read. Install ExifTool or use "
    "a packaged release, which bundles it."
)
REASON_DEVICE_REFUSED: Final = "The camera refused the read request."


def unavailable_line(message: str, reason: str) -> str:
    """Compose the one-line unavailable result, disclaimer included."""
    return f"{message}: {reason} {UNAVAILABLE_DISCLAIMER}"
