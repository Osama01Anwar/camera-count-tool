"""Reading counters out of metadata: exact field names only."""

from __future__ import annotations

from typing import Any

import pytest

from camera_count.core.enums import (
    CitationKind,
    CountType,
    MethodType,
    VerificationStatus,
)
from camera_count.core.messages import (
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    NOT_AN_ORIGINAL_CAMERA_FILE,
)
from camera_count.core.models import ShutterReading, Unavailable
from camera_count.core.sources import Citation, set_source_resolver
from camera_count.metadata.fields import (
    counters_from_tags,
    lookup_field,
    non_authoritative_counters,
    parse_counter_value,
)
from camera_count.metadata.originality import assess_originality
from camera_count.registry.models import CameraModel, RegisteredMethod
from tests.metadata.test_originality import original_jpeg

CITATION = Citation(
    kind=CitationKind.SOURCE_REF,
    reference="exiftool/lib/Image/ExifTool/Nikon.pm:1",
    note="test fixture",
)


def makernote_model(identifier: str = "Nikon:ShutterCount") -> CameraModel:
    return CameraModel(
        manufacturer="Nikon",
        model="NIKON Z 6_2",
        exact_count_available=True,
        methods=(
            RegisteredMethod(
                source_id="nikon/nikon-z-6-2#0",
                method_type=MethodType.MAKERNOTE_FIELD,
                identifier=identifier,
                count_type=CountType.TOTAL_RELEASES,
                verification_status=VerificationStatus.DOCUMENTED,
                citation=CITATION,
            ),
        ),
    )


@pytest.fixture
def resolver():
    def install(model: CameraModel) -> None:
        records = {record.source_id: record for record in model.source_records()}
        set_source_resolver(type("R", (), {"resolve": lambda self, i: records.get(i)})())

    previous = set_source_resolver(None)
    yield install
    set_source_resolver(previous)


def test_documented_field_produces_a_cited_reading(resolver) -> None:
    model = makernote_model()
    resolver(model)
    tags = original_jpeg()

    results = counters_from_tags(model, tags, assess_originality(tags))

    assert isinstance(results[0], ShutterReading)
    assert results[0].value == 12_345
    assert results[0].count_type is CountType.TOTAL_RELEASES
    assert results[0].transaction_ref == "Nikon:ShutterCount"


def test_a_non_original_file_yields_no_count_at_all(resolver) -> None:
    model = makernote_model()
    resolver(model)
    tags = original_jpeg(**{"IFD0:Software": "Adobe Photoshop 26.0"})

    results = counters_from_tags(model, tags, assess_originality(tags))

    assert isinstance(results[0], Unavailable)
    assert results[0].message == NOT_AN_ORIGINAL_CAMERA_FILE


def test_absent_field_is_reported_by_name(resolver) -> None:
    model = makernote_model("Nikon:SomeOtherCounter")
    resolver(model)
    tags = original_jpeg()

    results = counters_from_tags(model, tags, assess_originality(tags))

    assert isinstance(results[0], Unavailable)
    assert "Nikon:SomeOtherCounter" in results[0].reason


def test_unknown_model_never_falls_back_to_a_similar_field() -> None:
    tags = original_jpeg()

    results = counters_from_tags(None, tags, assess_originality(tags))

    assert isinstance(results[0], Unavailable)
    assert results[0].message == EXACT_SHUTTER_COUNT_NOT_AVAILABLE


def test_field_lookup_is_exact_about_the_group() -> None:
    tags = {"Nikon:ShutterCount": 10, "Canon:ShutterCount": 20}

    assert lookup_field(tags, "Nikon:ShutterCount") == ("Nikon:ShutterCount", 10)
    assert lookup_field(tags, "nikon:shuttercount") == ("Nikon:ShutterCount", 10)
    assert lookup_field(tags, "ShutterCount") is None
    assert lookup_field(tags, "Sony:ShutterCount") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (12345, 12345),
        ("12345", 12345),
        (0, 0),
        (-1, None),
        (True, None),
        ("12,345", None),
        ("about 12000", None),
        (12.5, None),
        (None, None),
        ([1, 2], None),
    ],
)
def test_counter_values_must_be_plain_integers(raw: Any, expected: int | None) -> None:
    assert parse_counter_value(raw) == expected


def test_non_integer_field_is_refused_rather_than_coerced(resolver) -> None:
    model = makernote_model()
    resolver(model)
    tags = original_jpeg(**{"Nikon:ShutterCount": "approximately 12000"})

    results = counters_from_tags(model, tags, assess_originality(tags))

    assert isinstance(results[0], Unavailable)
    assert "not a plain counter integer" in results[0].reason


def test_image_counters_are_collected_separately_never_as_a_count() -> None:
    tags = original_jpeg(
        **{"Canon:FileNumber": 1234, "ExifIFD:ImageNumber": 99, "Nikon:ShutterCount": 5}
    )

    counters = non_authoritative_counters(tags)

    labels = {counter.label for counter in counters}
    assert labels == {"FileNumber", "ImageNumber"}
    assert "ShutterCount" not in labels
