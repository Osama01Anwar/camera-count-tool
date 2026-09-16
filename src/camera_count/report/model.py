"""The data a Used Camera Inspection Report is built from.

Assembled once, then rendered to HTML, PDF or JSON, so every format says
exactly the same thing.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from camera_count import __version__
from camera_count.core.messages import (
    EXACT_COUNT_UNAVAILABLE,
    HISTORICAL_COUNTS_NOTICE,
    IMAGE_COUNTER_NOTICE,
    NOT_AVAILABLE,
    READ_ONLY_NOTICE,
    UNAVAILABLE_DISCLAIMER,
    VERIFIED_EXACT_COUNT,
)
from camera_count.core.models import (
    CameraIdentity,
    CounterSlot,
    NonAuthoritativeCounter,
    ShutterReading,
)
from camera_count.diagnostics.log import TransactionLog
from camera_count.inspection import InspectionResult

REPORT_TITLE = "Used Camera Inspection Report"

COUNTER_LABELS = {
    "mechanical": "Mechanical shutter",
    "electronic": "Electronic shutter",
    "efc": "Electronic first curtain",
    "total_releases": "Total releases",
}


def git_hash() -> str | None:
    """The commit this build came from, when running from a checkout."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            capture_output=True,
            timeout=5,
            check=False,
            shell=False,
            cwd=Path(__file__).resolve().parent,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.decode("utf-8", errors="replace").strip() or None


@dataclass(frozen=True, slots=True)
class CounterLine:
    """One counter as it appears in the report."""

    label: str
    value: str
    count_type: str
    available: bool
    method: str = NOT_AVAILABLE
    identifier: str = NOT_AVAILABLE
    status: str = NOT_AVAILABLE
    citation: str = NOT_AVAILABLE
    transaction: str = NOT_AVAILABLE
    message: str = ""
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ImageEvidence:
    """One file the report relies on."""

    file_name: str
    path: str
    size_bytes: int
    sha256: str
    file_type: str
    capture_date: str
    is_original: bool
    originality_reason: str
    field_used: str


@dataclass(frozen=True, slots=True)
class ReportData:
    """Everything a report states, in one place."""

    generated_utc: str
    generated_local: str
    app_version: str
    git_hash: str | None
    mode: str
    headline: str
    identity: CameraIdentity
    usb_summary: str
    protocol: str
    adapter: str
    registry_model: str
    counters: tuple[CounterLine, ...] = ()
    images: tuple[ImageEvidence, ...] = ()
    non_authoritative: tuple[NonAuthoritativeCounter, ...] = ()
    limitations: tuple[str, ...] = ()
    transaction_summary: tuple[str, ...] = ()
    transaction_count: int = 0
    seller_notes: str = ""
    buyer_notes: str = ""
    notices: tuple[str, ...] = field(default=())

    @property
    def exact_count_found(self) -> bool:
        return any(line.available for line in self.counters)


def _counter_line(slot: CounterSlot) -> CounterLine:
    label = COUNTER_LABELS.get(slot.count_type.value, slot.count_type.value)
    outcome = slot.result
    if isinstance(outcome, ShutterReading):
        return CounterLine(
            label=label,
            value=str(outcome.value),
            count_type=slot.count_type.value,
            available=True,
            method=outcome.source.method_type.value,
            identifier=outcome.source.identifier,
            status=outcome.source.verification_status.value,
            citation=outcome.source.citation.display(),
            transaction=outcome.transaction_ref or NOT_AVAILABLE,
        )
    return CounterLine(
        label=label,
        value=NOT_AVAILABLE,
        count_type=slot.count_type.value,
        available=False,
        message=outcome.message,
        reason=outcome.reason,
    )


def _timestamps() -> tuple[str, str]:
    now = datetime.now(UTC)
    return now.isoformat(timespec="seconds"), now.astimezone().isoformat(timespec="seconds")


def _log_summary(log: TransactionLog) -> tuple[str, ...]:
    return tuple(
        f"{record.reference}  {record.operation}  {record.response_name}" for record in log.records
    )


def from_inspection(
    result: InspectionResult,
    *,
    seller_notes: str = "",
    buyer_notes: str = "",
) -> ReportData:
    """Build report data from a camera inspection."""
    utc, local = _timestamps()
    device = result.device
    usb_summary = (
        f"{device.usb_ids} via {device.backend}; {device.describe_interfaces()}"
        if device
        else NOT_AVAILABLE
    )

    limitations: list[str] = list(result.model.limitations) if result.model else []
    notices = [READ_ONLY_NOTICE]
    if not result.has_exact_count:
        notices.append(UNAVAILABLE_DISCLAIMER)
    if result.failure is not None:
        limitations.append(f"{result.failure.message}: {result.failure.reason}")

    return ReportData(
        generated_utc=utc,
        generated_local=local,
        app_version=__version__,
        git_hash=git_hash(),
        mode="camera",
        headline=VERIFIED_EXACT_COUNT if result.has_exact_count else EXACT_COUNT_UNAVAILABLE,
        identity=result.identity,
        usb_summary=usb_summary,
        protocol=result.identity.protocol.value,
        adapter=result.adapter,
        registry_model=result.model.model if result.model else NOT_AVAILABLE,
        counters=tuple(_counter_line(slot) for slot in result.counters),
        limitations=tuple(limitations),
        transaction_summary=_log_summary(result.log),
        transaction_count=len(result.log),
        seller_notes=seller_notes,
        buyer_notes=buyer_notes,
        notices=tuple(notices),
    )


def from_image_analyses(
    analyses: Sequence[Any],
    *,
    seller_notes: str = "",
    buyer_notes: str = "",
) -> ReportData:
    """Build report data from one or more analysed files."""
    utc, local = _timestamps()
    first = analyses[0] if analyses else None
    found = any(getattr(item, "has_exact_count", False) for item in analyses)

    counters: list[CounterLine] = []
    images: list[ImageEvidence] = []
    non_authoritative: list[NonAuthoritativeCounter] = []
    limitations: list[str] = []

    for analysis in analyses:
        field_used = NOT_AVAILABLE
        for slot in analysis.counter_slots():
            line = _counter_line(slot)
            if line.available:
                field_used = line.identifier
            counters.append(line)
        images.append(
            ImageEvidence(
                file_name=analysis.path.name,
                path=str(analysis.path),
                size_bytes=analysis.size_bytes,
                sha256=analysis.sha256,
                file_type=analysis.file_type or NOT_AVAILABLE,
                capture_date=analysis.display_capture_date(),
                is_original=analysis.is_original,
                originality_reason=(
                    analysis.originality.reason if analysis.originality else NOT_AVAILABLE
                ),
                field_used=field_used,
            )
        )
        non_authoritative.extend(analysis.non_authoritative)
        if analysis.registry_model is not None:
            limitations.extend(analysis.registry_model.limitations)

    notices = [READ_ONLY_NOTICE]
    if found:
        notices.append(HISTORICAL_COUNTS_NOTICE)
    else:
        notices.append(UNAVAILABLE_DISCLAIMER)
    if non_authoritative:
        notices.append(IMAGE_COUNTER_NOTICE)

    identity = CameraIdentity(
        manufacturer=getattr(first, "make", None),
        model=getattr(first, "model", None),
    )

    return ReportData(
        generated_utc=utc,
        generated_local=local,
        app_version=__version__,
        git_hash=git_hash(),
        mode="image",
        headline=VERIFIED_EXACT_COUNT if found else EXACT_COUNT_UNAVAILABLE,
        identity=identity,
        usb_summary=NOT_AVAILABLE,
        protocol=NOT_AVAILABLE,
        adapter="metadata",
        registry_model=(
            getattr(getattr(first, "registry_model", None), "model", None) or NOT_AVAILABLE
        ),
        counters=tuple(counters),
        images=tuple(images),
        non_authoritative=tuple(dict.fromkeys(non_authoritative)),
        limitations=tuple(dict.fromkeys(limitations)),
        seller_notes=seller_notes,
        buyer_notes=buyer_notes,
        notices=tuple(notices),
    )
