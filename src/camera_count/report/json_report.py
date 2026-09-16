"""The canonical JSON form of a report, and the digest every format quotes.

The digest is taken over this structure rather than over the rendered HTML or
PDF, so the same value appears in all three. Two reports with the same digest
state the same facts, whatever format they were produced in.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from camera_count.report.model import ReportData


def to_dict(data: ReportData) -> dict[str, Any]:
    """The canonical content of a report."""
    return {
        "report": "Used Camera Inspection Report",
        "generated": {
            "utc": data.generated_utc,
            "local": data.generated_local,
        },
        "software": {
            "name": "Camera Count Tool",
            "version": data.app_version,
            "git_hash": data.git_hash,
            "mode": data.mode,
        },
        "headline": data.headline,
        "exact_count_found": data.exact_count_found,
        "camera": {
            "manufacturer": data.identity.display_manufacturer(),
            "model": data.identity.display_model(),
            "serial": data.identity.display_serial(),
            "firmware": data.identity.display_firmware(),
            "protocol": data.protocol,
            "usb": data.usb_summary,
            "adapter": data.adapter,
            "registry_model": data.registry_model,
        },
        "counters": [
            {
                "counter": line.count_type,
                "label": line.label,
                "available": line.available,
                "value": line.value,
                "method": line.method,
                "identifier": line.identifier,
                "verification_status": line.status,
                "citation": line.citation,
                "transaction": line.transaction,
                "message": line.message,
                "reason": line.reason,
            }
            for line in data.counters
        ],
        "image_evidence": [
            {
                "file_name": image.file_name,
                "path": image.path,
                "size_bytes": image.size_bytes,
                "sha256": image.sha256,
                "file_type": image.file_type,
                "capture_date": image.capture_date,
                "is_original": image.is_original,
                "originality": image.originality_reason,
                "field_used": image.field_used,
            }
            for image in data.images
        ],
        "non_authoritative_counters": [
            {"label": counter.label, "value": counter.value, "origin": counter.origin}
            for counter in data.non_authoritative
        ],
        "limitations": list(data.limitations),
        "notices": list(data.notices),
        "inspection_log": {
            "transaction_count": data.transaction_count,
            "entries": list(data.transaction_summary),
        },
        "notes": {"seller": data.seller_notes, "buyer": data.buyer_notes},
    }


def canonical_json(data: ReportData) -> str:
    return json.dumps(to_dict(data), indent=2, sort_keys=True, ensure_ascii=False)


def content_digest(data: ReportData) -> str:
    """SHA-256 over the canonical content, for tamper evidence."""
    payload = json.dumps(to_dict(data), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def render_json(data: ReportData) -> str:
    """The JSON report, with its own digest included."""
    document = to_dict(data)
    document["content_sha256"] = content_digest(data)
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
