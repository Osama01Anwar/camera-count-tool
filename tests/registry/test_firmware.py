"""Firmware ranges: when in doubt, do not read."""

from __future__ import annotations

import pytest

from camera_count.registry.firmware import firmware_matches, parse_version


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.40", (1, 40)),
        ("Ver.1.03", (1, 3)),
        ("2", (2,)),
        ("", None),
        (None, None),
        ("unknown", None),
    ],
)
def test_version_parsing(text: str | None, expected: tuple[int, ...] | None) -> None:
    assert parse_version(text) == expected


@pytest.mark.parametrize(
    ("spec", "firmware", "expected"),
    [
        (None, "1.40", True),
        ("*", "1.40", True),
        ("*", None, True),
        (">=1.30", "1.40", True),
        (">=1.30", "1.30", True),
        (">=1.30", "1.20", False),
        ("<=2.00", "1.40", True),
        ("<=2.00", "2.10", False),
        (">1.30", "1.30", False),
        ("<2.00", "1.99", True),
        ("1.30-2.00", "1.40", True),
        ("1.30-2.00", "1.20", False),
        ("1.30-2.00", "2.10", False),
        ("1.40", "1.40", True),
        ("1.40", "1.41", False),
    ],
)
def test_range_matching(spec: str | None, firmware: str | None, expected: bool) -> None:
    assert firmware_matches(spec, firmware) is expected


def test_unknown_firmware_never_satisfies_a_real_range() -> None:
    assert firmware_matches(">=1.30", None) is False
    assert firmware_matches("1.40", "") is False


def test_unparseable_spec_is_refused_rather_than_ignored() -> None:
    assert firmware_matches("somewhere around 1.4", "1.40") is False
    assert firmware_matches(">=", "1.40") is False


def test_shorter_version_compares_as_zero_padded() -> None:
    assert firmware_matches(">=1.3", "1.3.0") is True
    assert firmware_matches("<=1.3", "1.3.1") is False
