"""Finding and invoking ExifTool, and coping when it is absent.

These do not depend on what happens to be installed on the machine running
them, which is the point: the behaviour must be the same on a developer's
laptop, on a build runner, and inside a packaged release.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from camera_count.core.errors import MetadataError, ToolNotFoundError
from camera_count.metadata import analyze as analyze_module
from camera_count.metadata import exiftool as exiftool_module
from camera_count.metadata.analyze import (
    FileAnalysis,
    analyze_files,
    historical_notice,
    sha256_of,
)
from camera_count.metadata.exiftool import (
    build_command,
    exiftool_info,
    find_exiftool,
    find_perl,
)

# --- locating -----------------------------------------------------------------


def test_an_executable_runs_directly(tmp_path: Path) -> None:
    executable = tmp_path / "exiftool.exe"
    executable.write_bytes(b"")

    assert build_command(executable) == [str(executable)]


def test_a_perl_script_needs_an_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "exiftool"
    script.write_text("#!/usr/bin/perl\n", encoding="utf-8")
    perl = tmp_path / "perl.exe"
    perl.write_bytes(b"")
    monkeypatch.setattr(exiftool_module, "find_perl", lambda: perl)

    assert build_command(script) == [str(perl), str(script)]


def test_a_perl_script_without_perl_is_reported_clearly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "exiftool"
    script.write_text("#!/usr/bin/perl\n", encoding="utf-8")
    monkeypatch.setattr(exiftool_module, "find_perl", lambda: None)

    with pytest.raises(ToolNotFoundError, match="no Perl interpreter"):
        build_command(script)


def test_an_executable_on_path_is_preferred_over_a_perl_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A working exe beats a script that needs an interpreter."""
    on_path = tmp_path / "exiftool.exe"
    on_path.write_bytes(b"")
    monkeypatch.setattr(exiftool_module.shutil, "which", lambda name: str(on_path))
    monkeypatch.delenv(exiftool_module.EXIFTOOL_ENV, raising=False)

    candidates = exiftool_module._candidate_paths()
    executables = [item for item in candidates if item.suffix == ".exe"]
    scripts = [item for item in candidates if item.suffix == ""]

    assert on_path in candidates
    if scripts:
        assert candidates.index(on_path) < candidates.index(scripts[0])
    assert executables


def test_the_environment_variable_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    chosen = tmp_path / "my-exiftool.exe"
    chosen.write_bytes(b"")
    monkeypatch.setenv(exiftool_module.EXIFTOOL_ENV, str(chosen))

    assert exiftool_module._candidate_paths()[0] == chosen
    assert find_exiftool() == chosen


def test_a_missing_exiftool_says_how_to_fix_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(exiftool_module, "_candidate_paths", list)

    with pytest.raises(ToolNotFoundError, match="ExifTool was not found"):
        find_exiftool()


def test_perl_discovery_returns_a_path_or_nothing() -> None:
    found = find_perl()

    assert found is None or found.is_file()


def test_version_lookup_uses_the_given_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "exiftool.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(exiftool_module, "_run", lambda command, timeout: "13.59\n")

    info = exiftool_info(executable)

    assert info.version == "13.59"
    assert info.interpreter is None
    assert "13.59" in info.describe()


# --- analysing without ExifTool -----------------------------------------------


def test_no_files_means_no_work() -> None:
    assert analyze_files([]) == ()


def test_a_missing_exiftool_still_hashes_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = tmp_path / "photo.jpg"
    sample.write_bytes(b"not really a jpeg, but it is a real file")

    def refuse(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise ToolNotFoundError("ExifTool was not found")

    monkeypatch.setattr(analyze_module, "read_metadata", refuse)

    analyses = analyze_files([sample])

    assert len(analyses) == 1
    analysis = analyses[0]
    assert analysis.sha256 == sha256_of(sample)
    assert analysis.size_bytes == sample.stat().st_size
    assert not analysis.has_exact_count
    assert "ExifTool was not found" in analysis.results[0].reason  # type: ignore[union-attr]


def test_a_file_with_no_metadata_at_all_is_reported_not_guessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sample = tmp_path / "photo.jpg"
    sample.write_bytes(b"bytes")
    monkeypatch.setattr(analyze_module, "read_metadata", lambda paths: [])

    analysis = analyze_files([sample])[0]

    assert analysis.make is None
    assert not analysis.has_exact_count
    assert "No metadata could be read" in analysis.results[0].reason  # type: ignore[union-attr]
    assert analysis.originality is None


def test_hashing_matches_hashlib(tmp_path: Path) -> None:
    import hashlib

    sample = tmp_path / "data.bin"
    payload = b"camera count tool" * 1000
    sample.write_bytes(payload)

    assert sha256_of(sample) == hashlib.sha256(payload).hexdigest()


def test_the_historical_notice_appears_only_when_a_count_was_found(
    tmp_path: Path,
) -> None:
    empty = FileAnalysis(path=tmp_path / "a.jpg", size_bytes=1, sha256="x")

    assert historical_notice([empty]) is None


def test_reading_refuses_a_file_that_is_not_there(tmp_path: Path) -> None:
    with pytest.raises(MetadataError):
        analyze_module.read_metadata([tmp_path / "missing.jpg"])
