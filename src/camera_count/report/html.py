"""The HTML report.

Self-contained by necessity as much as by design: this program makes no network
requests, so there are no web fonts, no CDN stylesheets and no remote images.
Everything a buyer needs is in the one file, and it prints sensibly.

Every value is escaped. Camera and file data is untrusted input, and a model
name is not allowed to become markup.
"""

from __future__ import annotations

from html import escape

from camera_count.core.messages import NOT_AVAILABLE
from camera_count.report.json_report import content_digest
from camera_count.report.model import REPORT_TITLE, ReportData

STYLE = """
:root {
  --ink: #16181d;
  --muted: #5b6270;
  --line: #d7dbe3;
  --paper: #ffffff;
  --panel: #f6f7f9;
  --found: #0f5132;
  --absent: #5b6270;
}
* { box-sizing: border-box; }
body {
  margin: 0 auto;
  padding: 32px 24px 64px;
  max-width: 900px;
  background: var(--paper);
  color: var(--ink);
  font: 15px/1.55 "Segoe UI", system-ui, -apple-system, sans-serif;
}
h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 0.08em;
     color: var(--muted); margin: 32px 0 12px; }
.sub { color: var(--muted); margin: 0 0 24px; }
.headline { padding: 18px 20px; border: 2px solid var(--ink); border-radius: 6px;
            font-size: 20px; font-weight: 700; letter-spacing: 0.02em; }
.headline.found { border-color: var(--found); color: var(--found); }
.headline.absent { border-color: var(--absent); color: var(--absent); }
table { width: 100%; border-collapse: collapse; margin: 0 0 8px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line);
         vertical-align: top; }
th { width: 200px; color: var(--muted); font-weight: 600; }
.counter { border: 1px solid var(--line); border-radius: 6px; padding: 14px 16px;
           margin-bottom: 10px; background: var(--panel); }
.counter .name { font-weight: 600; }
.counter .value { font-size: 28px; font-variant-numeric: tabular-nums; margin: 4px 0; }
.counter .value.absent { font-size: 18px; color: var(--muted); }
.meta { color: var(--muted); font-size: 13px; }
code, .mono { font-family: Consolas, "Courier New", monospace; font-size: 13px;
              word-break: break-all; }
ul { margin: 0 0 8px; padding-left: 20px; }
li { margin-bottom: 4px; }
.notice { border-left: 3px solid var(--line); padding: 6px 0 6px 12px;
          color: var(--muted); margin-bottom: 8px; }
footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--line);
         color: var(--muted); font-size: 12px; }
@media print {
  body { padding: 0; max-width: none; }
  .counter { break-inside: avoid; }
}
"""


def _row(label: str, value: str) -> str:
    return f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"


def _counter_block(line: object) -> str:
    available = getattr(line, "available", False)
    name = escape(getattr(line, "label", ""))
    if available:
        return (
            '<div class="counter">'
            f'<div class="name">{name}</div>'
            f'<div class="value">{escape(getattr(line, "value", ""))}</div>'
            '<div class="meta">'
            f"Source: {escape(getattr(line, 'method', ''))} "
            f"<code>{escape(getattr(line, 'identifier', ''))}</code><br>"
            f"Status: {escape(getattr(line, 'status', ''))}<br>"
            f'Cited: <span class="mono">{escape(getattr(line, "citation", ""))}</span><br>'
            f"Transaction: <code>{escape(getattr(line, 'transaction', ''))}</code>"
            "</div></div>"
        )
    return (
        '<div class="counter">'
        f'<div class="name">{name}</div>'
        f'<div class="value absent">{escape(NOT_AVAILABLE)}</div>'
        '<div class="meta">'
        f"{escape(getattr(line, 'message', ''))}<br>{escape(getattr(line, 'reason', ''))}"
        "</div></div>"
    )


def render_html(data: ReportData) -> str:
    """Render the full report as one self-contained HTML document."""
    digest = content_digest(data)
    found = data.exact_count_found
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(REPORT_TITLE)}</title>",
        f"<style>{STYLE}</style>",
        "</head><body>",
        f"<h1>{escape(REPORT_TITLE)}</h1>",
        f'<p class="sub">Generated {escape(data.generated_local)} '
        f"(UTC {escape(data.generated_utc)})</p>",
        f'<div class="headline {"found" if found else "absent"}">{escape(data.headline)}</div>',
        "<h2>Camera</h2><table>",
        _row("Manufacturer", data.identity.display_manufacturer()),
        _row("Model", data.identity.display_model()),
        _row("Serial number", data.identity.display_serial()),
        _row("Firmware", data.identity.display_firmware()),
        _row("Protocol", data.protocol),
        _row("USB", data.usb_summary),
        _row("Adapter", data.adapter),
        _row("Registry entry", data.registry_model),
        "</table>",
        "<h2>Counters</h2>",
    ]

    parts.extend(_counter_block(line) for line in data.counters)

    if data.non_authoritative:
        parts.append("<h2>Other counters found</h2>")
        parts.append(
            '<div class="notice">These are not shutter counts and are shown only '
            "for completeness.</div><ul>"
        )
        parts.extend(
            f"<li>{escape(counter.label)}: {escape(counter.value)} "
            f'<span class="meta">(from {escape(counter.origin)})</span></li>'
            for counter in data.non_authoritative
        )
        parts.append("</ul>")

    if data.images:
        parts.append("<h2>Image evidence</h2>")
        for image in data.images:
            parts.append("<table>")
            parts.append(_row("File", image.file_name))
            parts.append(_row("Full path", image.path))
            parts.append(_row("Size", f"{image.size_bytes} bytes"))
            parts.append(_row("SHA-256", image.sha256))
            parts.append(_row("Format", image.file_type))
            parts.append(_row("Captured", image.capture_date))
            parts.append(_row("Original camera file", "yes" if image.is_original else "no"))
            parts.append(_row("Originality check", image.originality_reason))
            parts.append(_row("Field used", image.field_used))
            parts.append("</table>")

    if data.limitations:
        parts.append("<h2>Limitations</h2><ul>")
        parts.extend(f"<li>{escape(item)}</li>" for item in data.limitations)
        parts.append("</ul>")

    if data.seller_notes or data.buyer_notes:
        parts.append("<h2>Notes</h2><table>")
        if data.seller_notes:
            parts.append(_row("Seller", data.seller_notes))
        if data.buyer_notes:
            parts.append(_row("Buyer", data.buyer_notes))
        parts.append("</table>")

    parts.append("<h2>Inspection log</h2>")
    if data.transaction_summary:
        parts.append(f'<p class="meta">{data.transaction_count} transactions.</p><ul>')
        parts.extend(f'<li class="mono">{escape(entry)}</li>' for entry in data.transaction_summary)
        parts.append("</ul>")
    else:
        parts.append('<p class="meta">No protocol transactions were performed.</p>')

    for notice in data.notices:
        parts.append(f'<div class="notice">{escape(notice)}</div>')

    parts.append(
        "<footer>"
        f"Camera Count Tool {escape(data.app_version)}"
        + (f" ({escape(data.git_hash)})" if data.git_hash else "")
        + "<br>Content SHA-256: "
        f'<span class="mono">{escape(digest)}</span>'
        "<br>The digest covers this report's content in its canonical JSON form, "
        "so the same value appears in the HTML, PDF and JSON versions of this "
        "report."
        "</footer>"
    )
    parts.append("</body></html>")
    return "\n".join(parts)
