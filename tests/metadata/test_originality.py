"""Original-file checks, driven by ExifTool-shaped tag dictionaries."""

from __future__ import annotations

from typing import Any

import pytest

from camera_count.metadata.originality import (
    assess_originality,
    find_tag,
    has_maker_notes,
    tag_group,
    tag_name,
)


def original_jpeg(**overrides: Any) -> dict[str, Any]:
    """A tag set shaped like ExifTool -G1 output for a straight-from-camera JPEG."""
    tags: dict[str, Any] = {
        "SourceFile": "DSC_0001.JPG",
        "File:FileType": "JPEG",
        "File:ImageWidth": 6000,
        "File:ImageHeight": 4000,
        "IFD0:Make": "NIKON CORPORATION",
        "IFD0:Model": "NIKON Z 6_2",
        "IFD0:Software": "Ver.1.40",
        "ExifIFD:ExifImageWidth": 6000,
        "ExifIFD:ExifImageHeight": 4000,
        "ExifIFD:DateTimeOriginal": "2025:06:01 10:00:00",
        "Nikon:ShutterCount": 12_345,
    }
    tags.update(overrides)
    return tags


def test_a_straight_from_camera_file_passes() -> None:
    verdict = assess_originality(original_jpeg())

    assert verdict.is_original
    assert verdict.failures == ()


def test_missing_maker_notes_fails() -> None:
    tags = original_jpeg()
    del tags["Nikon:ShutterCount"]

    verdict = assess_originality(tags)

    assert not verdict.is_original
    assert any(check.name == "maker notes" for check in verdict.failures)


def test_missing_make_and_model_fails() -> None:
    tags = original_jpeg()
    del tags["IFD0:Make"]
    del tags["IFD0:Model"]

    verdict = assess_originality(tags)

    assert not verdict.is_original
    assert any(check.name == "camera identification" for check in verdict.failures)


@pytest.mark.parametrize(
    "software",
    [
        "Adobe Photoshop 26.0 (Windows)",
        "Adobe Lightroom Classic 14.1",
        "GIMP 2.10.38",
        "Capture One 23",
        "Adobe DNG Converter 16.0",
        "Snapseed",
    ],
)
def test_editor_software_fails(software: str) -> None:
    verdict = assess_originality(original_jpeg(**{"IFD0:Software": software}))

    assert not verdict.is_original
    assert any(check.name == "editing software" for check in verdict.failures)


def test_camera_firmware_in_software_is_fine() -> None:
    verdict = assess_originality(original_jpeg(**{"IFD0:Software": "Ver.1.40"}))

    assert verdict.is_original


def test_resized_jpeg_fails_the_dimension_check() -> None:
    verdict = assess_originality(
        original_jpeg(**{"File:ImageWidth": 1920, "File:ImageHeight": 1280})
    )

    assert not verdict.is_original
    failure = next(check for check in verdict.failures if check.name == "dimensions")
    assert "resized" in failure.detail


def test_raw_files_skip_the_dimension_check() -> None:
    """In a raw file the EXIF size can describe a preview, so the check is not run."""
    verdict = assess_originality(
        original_jpeg(
            **{
                "File:FileType": "NEF",
                "File:ImageWidth": 6048,
                "ExifIFD:ExifImageWidth": 6000,
            }
        )
    )

    dimensions = next(check for check in verdict.checks if check.name == "dimensions")
    assert dimensions.passed
    assert "only holds for JPEG" in dimensions.detail


def test_screenshot_format_fails() -> None:
    verdict = assess_originality(original_jpeg(**{"File:FileType": "PNG"}))

    assert not verdict.is_original
    assert any(check.name == "file type" for check in verdict.failures)


def test_exiftool_warning_fails_integrity() -> None:
    verdict = assess_originality(
        original_jpeg(**{"ExifTool:Warning": "Truncated MakerNotes directory"})
    )

    assert not verdict.is_original
    assert any(check.name == "metadata integrity" for check in verdict.failures)


def test_minor_warning_is_tolerated() -> None:
    verdict = assess_originality(
        original_jpeg(**{"ExifTool:Warning": "[minor] Unrecognised MakerNotes"})
    )

    assert verdict.is_original


def test_verdict_reason_lists_every_failure() -> None:
    tags = original_jpeg(**{"IFD0:Software": "Adobe Photoshop 26.0"})
    del tags["Nikon:ShutterCount"]

    verdict = assess_originality(tags)

    assert "MakerNotes" in verdict.reason
    assert "editor" in verdict.reason


# --- helpers -----------------------------------------------------------------


def test_group_and_name_splitting() -> None:
    assert tag_group("Nikon:ShutterCount") == "Nikon"
    assert tag_name("Nikon:ShutterCount") == "ShutterCount"
    assert tag_group("SourceFile") == ""
    assert tag_name("SourceFile") == "SourceFile"


def test_maker_note_detection() -> None:
    assert has_maker_notes({"Canon:CanonImageType": "x"})
    assert has_maker_notes({"MakerNotes:Whatever": 1})
    assert not has_maker_notes({"File:FileType": "JPEG", "XMP-dc:Title": "t"})


def test_find_tag_ignores_group_and_case() -> None:
    found = find_tag({"IFD0:Make": "NIKON CORPORATION"}, "make")

    assert found == ("IFD0:Make", "NIKON CORPORATION")
    assert find_tag({}, "Make") is None
