"""Deciding whether a file is an original camera file.

A count read from an edited or re-saved file is worthless: the metadata may
have been copied, rewritten, or invented by whatever produced the copy. So the
originality checks run first, and a file that fails them yields no count at
all - not a count with a caveat.

Every check states what it looked at, so a seller and a buyer can both see why
a file was rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

#: Family-1 groups ExifTool uses for manufacturer MakerNotes. A file with none
#: of these has no MakerNotes, and MakerNotes are where counters live.
MAKER_GROUPS: Final[frozenset[str]] = frozenset(
    {
        "MakerNotes",
        "Canon",
        "CanonCustom",
        "CanonRaw",
        "Nikon",
        "NikonCapture",
        "NikonCustom",
        "NikonScan",
        "Sony",
        "SonyIDC",
        "FujiFilm",
        "Panasonic",
        "Olympus",
        "Pentax",
        "Ricoh",
        "Leica",
        "Sigma",
        "Hasselblad",
        "PhaseOne",
        "Casio",
        "Kodak",
        "Minolta",
        "Samsung",
        "Apple",
        "GoPro",
        "DJI",
        "Reconyx",
        "FLIR",
    }
)

#: Substrings that identify editing software in a Software-like tag. A camera
#: normally writes its firmware version there instead.
#:
#: The manufacturers' own editors matter as much as the third-party ones, and
#: are easier to miss: a file saved by Nikon Capture, Canon DPP or Sony Imaging
#: Edge has been rewritten by software, whatever badge is on it. So has a file
#: that ExifTool itself has written to.
EDITOR_SIGNATURES: Final[tuple[str, ...]] = (
    # Manufacturer editors and utilities
    "nikon capture",
    "capture editor",
    "capture nx",
    "viewnx",
    "nx studio",
    "nikon transfer",
    "digital photo professional",
    "canon utilities",
    "imaging edge",
    "sony raw driver",
    "olympus workspace",
    "olympus viewer",
    "om workspace",
    "raw file converter",
    "silkypix",
    "phocus",
    "fujifilm x raw studio",
    "photofunstudio",
    "pentax digital camera utility",
    "sigma photo pro",
    # Metadata tools: if one of these wrote the file, it is not untouched
    "exiftool",
    "exifeditor",
    "metadata++",
    # Third-party editors and pipelines
    "photoshop",
    "lightroom",
    "camera raw",
    "gimp",
    "affinity",
    "capture one",
    "luminar",
    "snapseed",
    "picasa",
    "paint.net",
    "irfanview",
    "darktable",
    "rawtherapee",
    "dxo",
    "topaz",
    "pixelmator",
    "acdsee",
    "corel",
    "photoscape",
    "faststone",
    "imagemagick",
    "ffmpeg",
    "instagram",
    "whatsapp",
    "facebook",
    "google photos",
    "windows photo",
    "dng converter",
    "preview.app",
    "photos 1",
)

#: File types a camera itself writes.
ORIGINAL_FILE_TYPES: Final[frozenset[str]] = frozenset(
    {
        "JPEG",
        "HEIC",
        "HEIF",
        "TIFF",
        "DNG",
        "CR2",
        "CR3",
        "CRW",
        "NEF",
        "NRW",
        "ARW",
        "ARQ",
        "SR2",
        "SRF",
        "RAF",
        "RW2",
        "RWL",
        "ORF",
        "ORI",
        "PEF",
        "SRW",
        "3FR",
        "FFF",
        "IIQ",
        "X3F",
        "MRW",
        "GPR",
        "DCR",
        "KDC",
        "MOS",
        "ERF",
    }
)

SOFTWARE_TAGS: Final[tuple[str, ...]] = (
    "Software",
    "ProcessingSoftware",
    "CreatorTool",
    "HistorySoftwareAgent",
)


@dataclass(frozen=True, slots=True)
class Check:
    """One originality check and what it saw."""

    name: str
    passed: bool
    detail: str

    def describe(self) -> str:
        return f"[{'ok' if self.passed else 'fail'}] {self.name}: {self.detail}"


@dataclass(frozen=True, slots=True)
class OriginalityVerdict:
    """Whether the file may be treated as an original camera file."""

    is_original: bool
    checks: tuple[Check, ...]

    @property
    def failures(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if not check.passed)

    @property
    def reason(self) -> str:
        if self.is_original:
            return "The file passes every original-camera-file check."
        return " ".join(check.detail for check in self.failures)


def tag_group(key: str) -> str:
    return key.split(":", 1)[0] if ":" in key else ""


def tag_name(key: str) -> str:
    return key.split(":", 1)[1] if ":" in key else key


def find_tag(tags: dict[str, Any], name: str) -> tuple[str, Any] | None:
    """Find a tag by bare name, whichever group it is in."""
    for key, value in tags.items():
        if tag_name(key).casefold() == name.casefold():
            return key, value
    return None


def _first_value(tags: dict[str, Any], names: tuple[str, ...]) -> tuple[str, Any] | None:
    for name in names:
        found = find_tag(tags, name)
        if found is not None:
            return found
    return None


def has_maker_notes(tags: dict[str, Any]) -> bool:
    return any(tag_group(key) in MAKER_GROUPS for key in tags)


def assess_originality(tags: dict[str, Any]) -> OriginalityVerdict:
    """Run every check and return the verdict with its evidence."""
    checks: list[Check] = []

    make = find_tag(tags, "Make")
    model = find_tag(tags, "Model")
    identified = make is not None and model is not None
    checks.append(
        Check(
            "camera identification",
            identified,
            f"Make and Model are present ({make[1] if make else '?'} {model[1] if model else '?'})."
            if identified
            else "The file carries no EXIF Make and Model, so no model-specific "
            "field can be trusted.",
        )
    )

    maker_notes = has_maker_notes(tags)
    checks.append(
        Check(
            "maker notes",
            maker_notes,
            "MakerNotes are present."
            if maker_notes
            else "The file has no MakerNotes; they are stripped when a file is "
            "exported or re-saved.",
        )
    )

    software = _first_value(tags, SOFTWARE_TAGS)
    editor = None
    if software is not None:
        text = str(software[1]).casefold()
        editor = next((sig for sig in EDITOR_SIGNATURES if sig in text), None)
    if software is None:
        software_detail = "No software is recorded, as expected for a camera original."
    elif editor is None:
        software_detail = (
            f"{software[0]} says {software[1]!r}, which is not a known editor - "
            "cameras record their firmware version here."
        )
    else:
        software_detail = (
            f"{software[0]} says {software[1]!r}. {editor!r} identifies editing "
            "software, so this file was written by software rather than by the camera."
        )
    checks.append(Check("editing software", editor is None, software_detail))

    file_type = find_tag(tags, "FileType")
    type_ok = file_type is not None and str(file_type[1]).upper() in ORIGINAL_FILE_TYPES
    checks.append(
        Check(
            "file type",
            type_ok,
            f"{file_type[1]} is a format cameras write."
            if type_ok and file_type
            else f"{file_type[1] if file_type else 'unknown'} is not a format a "
            "camera writes directly.",
        )
    )

    checks.append(_dimension_check(tags, file_type[1] if file_type else ""))

    warning = find_tag(tags, "Warning")
    warning_text = str(warning[1]) if warning else ""
    serious = bool(warning_text) and "minor" not in warning_text.casefold()
    checks.append(
        Check(
            "metadata integrity",
            not serious,
            "No metadata warnings." if not serious else f"ExifTool reported: {warning_text}",
        )
    )

    return OriginalityVerdict(
        is_original=all(check.passed for check in checks), checks=tuple(checks)
    )


def _dimension_check(tags: dict[str, Any], file_type: str) -> Check:
    """Compare the camera's recorded dimensions with the actual ones.

    Only applied to JPEG and HEIC: in a raw file the EXIF dimensions can
    legitimately describe an embedded preview rather than the frame, and a
    check that misfires is worse than no check.
    """
    if str(file_type).upper() not in {"JPEG", "HEIC", "HEIF"}:
        return Check(
            "dimensions",
            True,
            f"Not checked for {file_type or 'this format'}; the comparison only "
            "holds for JPEG and HEIC.",
        )

    actual_w = find_tag(tags, "ImageWidth")
    actual_h = find_tag(tags, "ImageHeight")
    exif_w = find_tag(tags, "ExifImageWidth")
    exif_h = find_tag(tags, "ExifImageHeight")
    if not (actual_w and actual_h and exif_w and exif_h):
        return Check("dimensions", True, "The file does not record both sizes to compare.")

    try:
        same = int(actual_w[1]) == int(exif_w[1]) and int(actual_h[1]) == int(exif_h[1])
    except (TypeError, ValueError):
        return Check("dimensions", True, "The recorded sizes are not numbers to compare.")

    return Check(
        "dimensions",
        same,
        f"The frame is {actual_w[1]}x{actual_h[1]}, matching what the camera recorded."
        if same
        else f"The file is {actual_w[1]}x{actual_h[1]} but the camera recorded "
        f"{exif_w[1]}x{exif_h[1]}, so it has been resized.",
    )
