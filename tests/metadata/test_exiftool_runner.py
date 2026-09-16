"""The ExifTool runner: guards first, then a real invocation when one exists."""

from __future__ import annotations

from pathlib import Path

import pytest

from camera_count.core.errors import MetadataError, ToolNotFoundError
from camera_count.metadata.exiftool import (
    MAX_FILE_BYTES,
    build_command,
    check_readable,
    exiftool_info,
    find_exiftool,
    read_metadata,
)
from tests.conftest import REPO_ROOT


def exiftool_available() -> bool:
    try:
        build_command(find_exiftool())
    except ToolNotFoundError:
        return False
    return True


requires_exiftool = pytest.mark.skipif(
    not exiftool_available(), reason="ExifTool is not available on this machine"
)


# --- guards ------------------------------------------------------------------


def test_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MetadataError, match="not a file"):
        check_readable(tmp_path / "nothing.jpg")


def test_empty_file_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jpg"
    empty.touch()

    with pytest.raises(MetadataError, match="empty"):
        check_readable(empty)


def test_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MetadataError, match="not a file"):
        check_readable(tmp_path)


def test_oversized_file_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sample = tmp_path / "big.jpg"
    sample.write_bytes(b"x" * 1024)
    monkeypatch.setattr("camera_count.metadata.exiftool.MAX_FILE_BYTES", 10)

    with pytest.raises(MetadataError, match="larger than"):
        check_readable(sample)


def test_size_limit_is_a_real_bound() -> None:
    assert MAX_FILE_BYTES > 0


def test_traversal_style_path_is_resolved_before_use(tmp_path: Path) -> None:
    sample = tmp_path / "sample.jpg"
    sample.write_bytes(b"data")
    sneaky = tmp_path / "sub" / ".." / "sample.jpg"
    sneaky.parent.mkdir(parents=True, exist_ok=True)

    resolved = check_readable(sneaky)

    assert resolved == sample.resolve()


def test_no_paths_means_no_process_is_started() -> None:
    assert read_metadata([]) == []


# --- real invocation ---------------------------------------------------------


@requires_exiftool
def test_version_is_reported() -> None:
    info = exiftool_info()

    assert info.version
    assert info.executable.exists()
    assert "ExifTool" in info.describe()


@requires_exiftool
def test_reading_a_file_returns_grouped_tags() -> None:
    """Any file works: ExifTool always reports the File group."""
    documents = read_metadata([REPO_ROOT / "LICENSE"])

    assert len(documents) == 1
    tags = documents[0]
    assert "SourceFile" in tags
    assert any(key.startswith("File:") for key in tags), tags.keys()


@requires_exiftool
def test_unicode_and_spaces_in_paths_survive_the_argument_file(tmp_path: Path) -> None:
    awkward = tmp_path / "caméra count ünïcode.txt"
    awkward.write_text("not an image", encoding="utf-8")

    documents = read_metadata([awkward])

    assert len(documents) == 1
    assert Path(documents[0]["SourceFile"]).name == awkward.name
