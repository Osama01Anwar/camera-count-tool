"""The PDF report, rendered through Qt.

Qt is already a dependency for the desktop app, so PDF output needs nothing
extra: no print server, no headless browser, no native GTK stack. Qt's rich
text engine understands a conservative subset of HTML, so this module builds
its own plain markup rather than reusing the styled web report.

Rendering works without a desktop session when ``QT_QPA_PLATFORM=offscreen``
is set, which is what CI does.
"""

from __future__ import annotations

import os
from html import escape
from pathlib import Path
from typing import Any

from camera_count.core.errors import CameraCountError
from camera_count.core.messages import NOT_AVAILABLE
from camera_count.report.json_report import content_digest
from camera_count.report.model import REPORT_TITLE, ReportData

PDF_STYLE = (
    "body { font-family: 'Segoe UI', sans-serif; font-size: 10pt; color: #16181d; }"
    " h1 { font-size: 17pt; margin-bottom: 2px; }"
    " h2 { font-size: 11pt; margin-top: 16px; margin-bottom: 4px; color: #5b6270; }"
    " td, th { padding: 3px 6px; }"
    " th { text-align: left; color: #5b6270; }"
    " .headline { font-size: 14pt; font-weight: bold; }"
    " .muted { color: #5b6270; font-size: 9pt; }"
    " .count { font-size: 16pt; font-weight: bold; }"
)


def _rows(pairs: list[tuple[str, str]]) -> str:
    body = "".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>" for label, value in pairs
    )
    return f'<table width="100%" cellspacing="0" cellpadding="0">{body}</table>'


def _counter(line: Any) -> str:
    name = escape(getattr(line, "label", ""))
    if getattr(line, "available", False):
        return (
            f"<p><b>{name}</b><br>"
            f'<span class="count">{escape(getattr(line, "value", ""))}</span><br>'
            f'<span class="muted">Source: {escape(getattr(line, "method", ""))} '
            f"{escape(getattr(line, 'identifier', ''))} &middot; "
            f"status {escape(getattr(line, 'status', ''))}<br>"
            f"Cited: {escape(getattr(line, 'citation', ''))}<br>"
            f"Transaction: {escape(getattr(line, 'transaction', ''))}</span></p>"
        )
    return (
        f"<p><b>{name}</b><br>{escape(NOT_AVAILABLE)}<br>"
        f'<span class="muted">{escape(getattr(line, "message", ""))} '
        f"{escape(getattr(line, 'reason', ''))}</span></p>"
    )


def pdf_html(data: ReportData) -> str:
    """Conservative markup for Qt's rich text engine."""
    digest = content_digest(data)
    parts = [
        f"<html><head><style>{PDF_STYLE}</style></head><body>",
        f"<h1>{escape(REPORT_TITLE)}</h1>",
        f'<p class="muted">Generated {escape(data.generated_local)} '
        f"(UTC {escape(data.generated_utc)})</p>",
        f'<p class="headline">{escape(data.headline)}</p>',
        "<h2>Camera</h2>",
        _rows(
            [
                ("Manufacturer", data.identity.display_manufacturer()),
                ("Model", data.identity.display_model()),
                ("Serial number", data.identity.display_serial()),
                ("Firmware", data.identity.display_firmware()),
                ("Protocol", data.protocol),
                ("USB", data.usb_summary),
                ("Adapter", data.adapter),
                ("Registry entry", data.registry_model),
            ]
        ),
        "<h2>Counters</h2>",
    ]
    parts.extend(_counter(line) for line in data.counters)

    if data.non_authoritative:
        parts.append("<h2>Other counters found</h2>")
        parts.append('<p class="muted">These are not shutter counts.</p><ul>')
        parts.extend(
            f"<li>{escape(counter.label)}: {escape(counter.value)} "
            f"(from {escape(counter.origin)})</li>"
            for counter in data.non_authoritative
        )
        parts.append("</ul>")

    for image in data.images:
        parts.append("<h2>Image evidence</h2>")
        parts.append(
            _rows(
                [
                    ("File", image.file_name),
                    ("Size", f"{image.size_bytes} bytes"),
                    ("SHA-256", image.sha256),
                    ("Format", image.file_type),
                    ("Captured", image.capture_date),
                    ("Original camera file", "yes" if image.is_original else "no"),
                    ("Originality check", image.originality_reason),
                    ("Field used", image.field_used),
                ]
            )
        )

    if data.limitations:
        parts.append("<h2>Limitations</h2><ul>")
        parts.extend(f"<li>{escape(item)}</li>" for item in data.limitations)
        parts.append("</ul>")

    if data.seller_notes or data.buyer_notes:
        parts.append("<h2>Notes</h2>")
        parts.append(
            _rows(
                [
                    pair
                    for pair in (
                        ("Seller", data.seller_notes),
                        ("Buyer", data.buyer_notes),
                    )
                    if pair[1]
                ]
            )
        )

    parts.append("<h2>Inspection log</h2>")
    if data.transaction_summary:
        parts.append(f'<p class="muted">{data.transaction_count} transactions.</p><ul>')
        parts.extend(f"<li>{escape(entry)}</li>" for entry in data.transaction_summary)
        parts.append("</ul>")
    else:
        parts.append('<p class="muted">No protocol transactions were performed.</p>')

    for notice in data.notices:
        parts.append(f'<p class="muted">{escape(notice)}</p>')

    version = escape(data.app_version) + (f" ({escape(data.git_hash)})" if data.git_hash else "")
    parts.append(
        f'<p class="muted">Camera Count Tool {version}<br>'
        f"Content SHA-256: {escape(digest)}<br>"
        "The digest covers this report's content in its canonical JSON form, so "
        "the same value appears in the HTML, PDF and JSON versions.</p>"
    )
    parts.append("</body></html>")
    return "".join(parts)


def _ensure_qt_application() -> Any:
    """Return a Qt application instance, creating an offscreen one if needed."""
    try:
        from PySide6.QtGui import QGuiApplication  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - Qt is a hard dependency
        raise CameraCountError(
            "PDF output needs PySide6, which is part of a normal installation."
        ) from exc

    existing = QGuiApplication.instance()
    if existing is not None:
        return existing
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QGuiApplication([])


def render_pdf(data: ReportData, destination: Path) -> Path:
    """Write the report to ``destination`` as a PDF."""
    from PySide6.QtCore import QSizeF  # noqa: PLC0415
    from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument  # noqa: PLC0415

    _ensure_qt_application()

    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = QPdfWriter(str(destination))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setTitle(REPORT_TITLE)
    writer.setResolution(300)

    document = QTextDocument()
    document.setHtml(pdf_html(data))
    page = writer.pageLayout().paintRectPixels(writer.resolution())
    document.setPageSize(QSizeF(page.width(), page.height()))
    document.print_(writer)

    if not destination.is_file() or destination.stat().st_size == 0:
        raise CameraCountError(f"the PDF was not written: {destination}")
    return destination
