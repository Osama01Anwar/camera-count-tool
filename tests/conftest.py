"""Shared fixtures.

Nothing here touches real hardware, the network, or the user's application data
directory.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from camera_count.core.enums import (
    CitationKind,
    CountType,
    MethodType,
    VerificationStatus,
)
from camera_count.core.sources import Citation, SourceRecord, set_source_resolver

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "camera_count"


def make_source_record(
    source_id: str = "testmaker/testmodel#0",
    *,
    status: VerificationStatus = VerificationStatus.DOCUMENTED,
    count_type: CountType = CountType.MECHANICAL,
    method_type: MethodType = MethodType.PTP_PROPERTY,
    identifier: str = "0x0000",
) -> SourceRecord:
    """Build a source record for tests. Not a camera, not a fixture of one."""
    return SourceRecord(
        source_id=source_id,
        manufacturer="TestMaker",
        model="TestModel",
        method_type=method_type,
        identifier=identifier,
        count_type=count_type,
        verification_status=status,
        citation=Citation(
            kind=CitationKind.SOURCE_REF,
            reference="tests/conftest.py:1",
            note="test-only record",
        ),
    )


class StubResolver:
    """Resolver backed by a plain dict, for tests that need the guard satisfied."""

    def __init__(self, records: dict[str, SourceRecord]) -> None:
        self._records = records

    def resolve(self, source_id: str) -> SourceRecord | None:
        return self._records.get(source_id)


@pytest.fixture
def documented_source() -> Iterator[SourceRecord]:
    """Install a resolver that knows one documented source, then restore."""
    record = make_source_record()
    previous = set_source_resolver(StubResolver({record.source_id: record}))
    try:
        yield record
    finally:
        set_source_resolver(previous)


@pytest.fixture
def unverified_source() -> Iterator[SourceRecord]:
    """Install a resolver whose only source is unverified, then restore."""
    record = make_source_record("testmaker/untested#0", status=VerificationStatus.UNVERIFIED)
    previous = set_source_resolver(StubResolver({record.source_id: record}))
    try:
        yield record
    finally:
        set_source_resolver(previous)


@pytest.fixture
def no_resolver() -> Iterator[None]:
    """Guarantee no resolver is installed for the duration of the test."""
    previous = set_source_resolver(None)
    try:
        yield None
    finally:
        set_source_resolver(previous)


def iter_source_files(suffixes: tuple[str, ...] = (".py",)) -> Iterator[Path]:
    """Every shipped source file under src/camera_count."""
    for path in sorted(SRC_ROOT.rglob("*")):
        if path.is_file() and path.suffix in suffixes:
            yield path
