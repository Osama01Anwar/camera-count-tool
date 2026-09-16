"""Used Camera Inspection Report, in HTML, PDF or JSON."""

from __future__ import annotations

from camera_count.report.builder import (
    DEFAULT_STEMS,
    ReportFormat,
    render_text,
    write_report,
)
from camera_count.report.html import render_html
from camera_count.report.json_report import canonical_json, content_digest, render_json, to_dict
from camera_count.report.model import (
    REPORT_TITLE,
    CounterLine,
    ImageEvidence,
    ReportData,
    from_image_analyses,
    from_inspection,
    git_hash,
)

__all__ = [
    "DEFAULT_STEMS",
    "REPORT_TITLE",
    "CounterLine",
    "ImageEvidence",
    "ReportData",
    "ReportFormat",
    "canonical_json",
    "content_digest",
    "from_image_analyses",
    "from_inspection",
    "git_hash",
    "render_html",
    "render_json",
    "render_text",
    "to_dict",
    "write_report",
]
