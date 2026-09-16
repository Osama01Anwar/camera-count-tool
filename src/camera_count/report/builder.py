"""Building and writing reports in whichever format was asked for."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from camera_count.core.errors import CameraCountError
from camera_count.report.html import render_html
from camera_count.report.json_report import content_digest, render_json
from camera_count.report.model import ReportData


class ReportFormat(StrEnum):
    HTML = "html"
    PDF = "pdf"
    JSON = "json"


DEFAULT_STEMS: dict[ReportFormat, str] = {
    ReportFormat.HTML: "camera-count-report.html",
    ReportFormat.PDF: "camera-count-report.pdf",
    ReportFormat.JSON: "camera-count-report.json",
}


def render_text(data: ReportData, report_format: ReportFormat) -> str:
    """Render a text-based report. PDF is binary and is written directly."""
    if report_format is ReportFormat.HTML:
        return render_html(data)
    if report_format is ReportFormat.JSON:
        return render_json(data)
    raise CameraCountError(f"{report_format.value} is not a text format")


def write_report(
    data: ReportData, destination: Path, report_format: ReportFormat
) -> tuple[Path, str]:
    """Write the report and return the path and its content digest."""
    destination = destination.expanduser()
    if destination.is_dir():
        destination = destination / DEFAULT_STEMS[report_format]
    destination.parent.mkdir(parents=True, exist_ok=True)

    if report_format is ReportFormat.PDF:
        from camera_count.report.pdf import render_pdf  # noqa: PLC0415

        render_pdf(data, destination)
    else:
        destination.write_text(render_text(data, report_format), encoding="utf-8")

    return destination, content_digest(data)
