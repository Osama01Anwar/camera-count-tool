"""Integration tests against real camera files.

These run against the sample images that ship with the ExifTool distribution,
which land under ``packaging/vendor/`` when a developer runs::

    python scripts/fetch_exiftool.py --mode source

The samples are not copied into this repository, so these tests skip when the
vendored distribution is absent. What they prove is the thing unit tests
cannot: that the identifiers in the registry are the strings ExifTool actually
produces for a real file from that camera.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from camera_count.core.models import ShutterReading, Unavailable
from camera_count.metadata.analyze import analyze_files
from camera_count.metadata.exiftool import read_metadata
from camera_count.metadata.fields import counters_from_tags, lookup_field
from camera_count.metadata.originality import Check, OriginalityVerdict, assess_originality
from camera_count.registry import load_default_registry
from tests.conftest import REPO_ROOT

SAMPLES = sorted((REPO_ROOT / "packaging" / "vendor").glob("exiftool-*/t/images"))
SAMPLE_DIR = SAMPLES[-1] if SAMPLES else None

requires_samples = pytest.mark.skipif(
    SAMPLE_DIR is None,
    reason="run scripts/fetch_exiftool.py --mode source to fetch the ExifTool samples",
)

#: A verdict used to isolate the field-reading path from the originality path,
#: which has its own tests. The shipped samples are deliberately truncated to
#: 8x8 pixels, so they legitimately fail the real check.
TREAT_AS_ORIGINAL = OriginalityVerdict(
    is_original=True,
    checks=(Check("test harness", True, "originality is covered by its own tests"),),
)


def sample(name: str) -> Path:
    assert SAMPLE_DIR is not None
    path = SAMPLE_DIR / name
    if not path.is_file():
        pytest.skip(f"sample {name} is not in this ExifTool distribution")
    return path


@requires_samples
@pytest.mark.parametrize(
    ("filename", "identifier", "expected"),
    [
        ("Nikon.nef", "Nikon:ShutterCount", 3619),
        ("Pentax.jpg", "Pentax:ShutterCount", 1648),
        ("NikonD2Hs.jpg", "Nikon:ShutterCount", 2),
    ],
)
def test_registry_identifiers_match_real_exiftool_output(
    filename: str, identifier: str, expected: int
) -> None:
    """The registry names the tag exactly as ExifTool reports it for a real file."""
    documents = read_metadata([sample(filename)])

    found = lookup_field(documents[0], identifier)

    assert found is not None, f"{identifier} not in {sorted(documents[0])[:40]}"
    assert found[1] == expected


@requires_samples
def test_a_real_nikon_file_yields_a_cited_reading() -> None:
    registry = load_default_registry()
    documents = read_metadata([sample("Nikon.nef")])
    tags = documents[0]
    model = registry.find_model(tags.get("IFD0:Make"), tags.get("IFD0:Model"))

    assert model is not None, "the Nikon wildcard entry should match a real Nikon file"

    results = counters_from_tags(model, tags, TREAT_AS_ORIGINAL)
    readings = [result for result in results if isinstance(result, ShutterReading)]

    assert readings, [getattr(r, "reason", None) for r in results]
    reading = readings[0]
    assert reading.value == 3619
    assert reading.source.citation.reference.startswith("exiftool/lib/Image/ExifTool/Nikon.pm:")
    assert reading.transaction_ref == "Nikon:ShutterCount"


@requires_samples
def test_a_real_pentax_file_yields_the_decrypted_count() -> None:
    """Pentax stores this counter encrypted; the decrypted value is what is read."""
    registry = load_default_registry()
    tags = read_metadata([sample("Pentax.jpg")])[0]
    model = registry.find_model(tags.get("IFD0:Make"), tags.get("IFD0:Model"))

    assert model is not None
    results = counters_from_tags(model, tags, TREAT_AS_ORIGINAL)
    readings = [result for result in results if isinstance(result, ShutterReading)]

    assert readings and readings[0].value == 1648


@requires_samples
def test_a_truncated_sample_is_refused_end_to_end() -> None:
    """The shipped samples are 8x8 crops, and the dimension check catches that."""
    analyses = analyze_files([sample("NikonD2Hs.jpg")])
    analysis = analyses[0]

    assert analysis.make == "NIKON CORPORATION"
    assert analysis.model == "NIKON D2Hs"
    assert not analysis.is_original
    assert not analysis.has_exact_count
    assert isinstance(analysis.results[0], Unavailable)
    assert "resized" in analysis.originality.reason  # type: ignore[union-attr]


@requires_samples
def test_image_counters_in_a_real_file_never_become_shutter_counts() -> None:
    analysis = analyze_files([sample("NikonD2Hs.jpg")])[0]

    labels = {counter.label for counter in analysis.non_authoritative}

    assert "ImageCount" in labels
    assert not analysis.has_exact_count


@requires_samples
def test_a_camera_without_a_documented_method_reports_unavailable() -> None:
    """Canon's EOS Digital Rebel has no registered method, and stays unregistered."""
    tags = read_metadata([sample("Canon.jpg")])[0]
    registry = load_default_registry()

    model = registry.find_model(tags.get("IFD0:Make"), tags.get("IFD0:Model"))
    results = counters_from_tags(model, tags, assess_originality(tags))

    assert all(isinstance(result, Unavailable) for result in results)
