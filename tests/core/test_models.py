"""The construction guard, integer validation, and counter separation."""

from __future__ import annotations

import pytest

from camera_count.core.enums import CountType, VerificationStatus
from camera_count.core.errors import (
    ForbiddenConstructionError,
    UnknownSourceError,
    UnverifiedSourceError,
    ValueOutOfBoundsError,
)
from camera_count.core.messages import (
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    NOT_AVAILABLE,
    UNAVAILABLE_DISCLAIMER,
)
from camera_count.core.models import (
    UINT32_MAX,
    CameraIdentity,
    ShutterReading,
    Unavailable,
    build_counter_slots,
    first_reading,
    validate_count_value,
)
from camera_count.core.sources import SourceRecord


def test_direct_construction_is_refused(documented_source: SourceRecord) -> None:
    with pytest.raises(ForbiddenConstructionError):
        ShutterReading(value=1234, source=documented_source)


def test_factory_creates_reading_from_documented_source(
    documented_source: SourceRecord,
) -> None:
    reading = ShutterReading.from_source(value=12_345, source_id=documented_source.source_id)

    assert reading.value == 12_345
    assert reading.display_value() == "12345"
    assert reading.count_type is CountType.MECHANICAL
    assert reading.source.verification_status is VerificationStatus.DOCUMENTED
    assert reading.source.citation.reference


def test_unverified_source_cannot_produce_a_reading(
    unverified_source: SourceRecord,
) -> None:
    with pytest.raises(UnverifiedSourceError):
        ShutterReading.from_source(value=1, source_id=unverified_source.source_id)


def test_unknown_source_cannot_produce_a_reading(documented_source: SourceRecord) -> None:
    with pytest.raises(UnknownSourceError):
        ShutterReading.from_source(value=1, source_id="nobody/nothing#0")


def test_reading_requires_a_resolver_at_all(no_resolver: None) -> None:
    with pytest.raises(UnknownSourceError):
        ShutterReading.from_source(value=1, source_id="testmaker/testmodel#0")


@pytest.mark.parametrize(
    "bad_value",
    [-1, UINT32_MAX + 1, True, 1.0, "1234", None],
)
def test_invalid_counter_values_are_refused(bad_value: object) -> None:
    with pytest.raises(ValueOutOfBoundsError):
        validate_count_value(bad_value)


@pytest.mark.parametrize("good_value", [0, 1, UINT32_MAX])
def test_boundary_values_are_accepted(good_value: int) -> None:
    assert validate_count_value(good_value) == good_value


def test_unavailable_rejects_invented_messages() -> None:
    with pytest.raises(ValueError, match="fixed result messages"):
        Unavailable(message="PROBABLY AROUND 40000", reason="because")


def test_unavailable_always_carries_the_disclaimer() -> None:
    result = Unavailable(message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason="No documented method.")

    assert result.display_value() == NOT_AVAILABLE
    assert result.display_line().endswith(UNAVAILABLE_DISCLAIMER)


def test_counters_stay_separate_and_are_never_merged(
    documented_source: SourceRecord,
) -> None:
    reading = ShutterReading.from_source(value=500, source_id=documented_source.source_id)

    slots = build_counter_slots([reading])

    by_type = {slot.count_type: slot for slot in slots}
    assert len(slots) == len(CountType)
    assert by_type[CountType.MECHANICAL].result is reading
    for other in (CountType.ELECTRONIC, CountType.EFC, CountType.TOTAL_RELEASES):
        assert not by_type[other].has_value
        assert by_type[other].result.display_value() == NOT_AVAILABLE


def test_first_reading_skips_unavailable_results(documented_source: SourceRecord) -> None:
    unavailable = Unavailable(
        message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason="Nothing documented."
    )
    reading = ShutterReading.from_source(value=7, source_id=documented_source.source_id)

    assert first_reading([unavailable, reading]) is reading
    assert first_reading([unavailable]) is None


def test_identity_shows_not_available_for_unknown_fields() -> None:
    identity = CameraIdentity(manufacturer="TestMaker", model="TestModel")

    assert identity.display_serial() == NOT_AVAILABLE
    assert identity.display_firmware() == NOT_AVAILABLE
    assert identity.is_identified
