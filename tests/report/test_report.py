"""Reports say the same thing in every format, and never invent a number."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from camera_count.core.enums import CitationKind, CountType, MethodType, VerificationStatus
from camera_count.core.messages import (
    EXACT_COUNT_UNAVAILABLE,
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    NOT_AVAILABLE,
    UNAVAILABLE_DISCLAIMER,
    VERIFIED_EXACT_COUNT,
)
from camera_count.core.models import (
    CameraIdentity,
    NonAuthoritativeCounter,
    ShutterReading,
    Unavailable,
    build_counter_slots,
)
from camera_count.core.sources import Citation, SourceRecord, set_source_resolver
from camera_count.diagnostics.log import TransactionLog
from camera_count.inspection import InspectionResult
from camera_count.report import (
    ReportFormat,
    content_digest,
    from_inspection,
    render_html,
    render_json,
    to_dict,
    write_report,
)
from camera_count.report.pdf import pdf_html

RECORD = SourceRecord(
    source_id="maker/body#0",
    manufacturer="Maker",
    model="Body",
    method_type=MethodType.MAKERNOTE_FIELD,
    identifier="Maker:ShutterCount",
    count_type=CountType.MECHANICAL,
    verification_status=VerificationStatus.DOCUMENTED,
    citation=Citation(
        kind=CitationKind.SOURCE_REF, reference="exiftool/lib/Image/ExifTool/Maker.pm:1"
    ),
)


@pytest.fixture
def resolver():
    previous = set_source_resolver(
        type("R", (), {"resolve": lambda self, i: RECORD if i == RECORD.source_id else None})()
    )
    yield
    set_source_resolver(previous)


def inspection_with_count(resolver_installed: object = None) -> InspectionResult:
    reading = ShutterReading.from_source(
        value=48_120, source_id=RECORD.source_id, transaction_ref="txn-0001"
    )
    return InspectionResult(
        identity=CameraIdentity(
            manufacturer="Maker", model="Body", serial="SN123", firmware="1.40"
        ),
        adapter="maker",
        results=(reading,),
        counters=build_counter_slots([reading]),
        log=TransactionLog(transport="test"),
    )


def inspection_without_count() -> InspectionResult:
    unavailable = Unavailable(
        message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason="No documented method."
    )
    return InspectionResult(
        identity=CameraIdentity(manufacturer="Maker", model="Body"),
        adapter="generic_ptp",
        results=(unavailable,),
        counters=build_counter_slots([unavailable], absent_reason="No documented method."),
        log=TransactionLog(transport="test"),
    )


# --- content -----------------------------------------------------------------


def test_a_report_with_a_count_states_the_value_and_its_citation(resolver) -> None:
    data = from_inspection(inspection_with_count())

    assert data.headline == VERIFIED_EXACT_COUNT
    line = next(item for item in data.counters if item.available)
    assert line.value == "48120"
    assert line.citation.startswith("exiftool/")
    assert line.status == "documented"
    assert line.transaction == "txn-0001"


def test_a_report_without_a_count_carries_the_disclaimer() -> None:
    data = from_inspection(inspection_without_count())

    assert data.headline == EXACT_COUNT_UNAVAILABLE
    assert UNAVAILABLE_DISCLAIMER in data.notices
    assert all(not line.available for line in data.counters)
    assert all(line.value == NOT_AVAILABLE for line in data.counters)


def test_every_format_carries_the_same_digest(resolver) -> None:
    data = from_inspection(inspection_with_count())

    digest = content_digest(data)
    html = render_html(data)
    document = json.loads(render_json(data))

    assert digest in html
    assert document["content_sha256"] == digest
    assert digest in pdf_html(data)


def test_the_digest_changes_when_a_value_changes(resolver) -> None:
    first = from_inspection(inspection_with_count())
    second = from_inspection(inspection_without_count())

    assert content_digest(first) != content_digest(second)


def test_counters_stay_separate_in_the_report(resolver) -> None:
    data = from_inspection(inspection_with_count())

    labels = [line.label for line in data.counters]
    assert labels == [
        "Mechanical shutter",
        "Electronic shutter",
        "Electronic first curtain",
        "Total releases",
    ]
    assert sum(1 for line in data.counters if line.available) == 1


def test_untrusted_text_is_escaped_in_html() -> None:
    result = inspection_without_count()
    hostile = InspectionResult(
        identity=CameraIdentity(
            manufacturer="<script>alert('x')</script>", model='Body" onload="evil()'
        ),
        adapter=result.adapter,
        results=result.results,
        counters=result.counters,
        log=result.log,
    )

    html = render_html(from_inspection(hostile))

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert 'onload="evil()"' not in html


def test_non_authoritative_counters_are_labelled_as_such() -> None:
    data = from_inspection(inspection_without_count())
    data = type(data)(
        **{
            **{key: getattr(data, key) for key in data.__slots__},
            "non_authoritative": (
                NonAuthoritativeCounter(
                    label="FileNumber", value="1234", origin="Maker:FileNumber"
                ),
            ),
        }
    )

    html = render_html(data)
    document = to_dict(data)

    assert "not shutter counts" in html
    assert document["non_authoritative_counters"][0]["label"] == "FileNumber"
    assert all(not line["available"] for line in document["counters"])


# --- writing -----------------------------------------------------------------


@pytest.mark.parametrize("report_format", [ReportFormat.HTML, ReportFormat.JSON])
def test_text_reports_are_written(resolver, tmp_path: Path, report_format: ReportFormat) -> None:
    data = from_inspection(inspection_with_count())

    written, digest = write_report(data, tmp_path / f"report.{report_format.value}", report_format)

    assert written.is_file()
    assert digest in written.read_text(encoding="utf-8")


def test_a_directory_destination_gets_a_default_name(resolver, tmp_path: Path) -> None:
    data = from_inspection(inspection_with_count())

    written, _ = write_report(data, tmp_path, ReportFormat.HTML)

    assert written.parent == tmp_path
    assert written.name.endswith(".html")


@pytest.mark.gui
def test_pdf_is_written_as_a_real_pdf(resolver, tmp_path: Path) -> None:
    data = from_inspection(inspection_with_count())

    written, _ = write_report(data, tmp_path / "report.pdf", ReportFormat.PDF)

    assert written.is_file()
    assert written.read_bytes().startswith(b"%PDF-")
    assert written.stat().st_size > 1000
