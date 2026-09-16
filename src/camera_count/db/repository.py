"""The local results database.

Everything stays on this machine. The only personal data stored is whatever the
user types into a report as seller or buyer notes.

Storing a reading goes through the same gate as displaying one: the schema
refuses a row that has a number without a trusted, cited source, so a bug in
the application layer cannot quietly persist an unsourced count.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Final

from camera_count import __version__
from camera_count.core.models import ShutterReading, Unavailable
from camera_count.diagnostics.log import TransactionLog
from camera_count.inspection import InspectionResult

APP_NAME: Final = "CameraCountTool"
DATABASE_FILENAME: Final = "camera-count.sqlite"
SCHEMA_VERSION: Final = 1


def default_database_path() -> Path:
    """The per-user data location, created on first use."""
    from platformdirs import user_data_dir  # noqa: PLC0415

    directory = Path(user_data_dir(APP_NAME, appauthor=False))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / DATABASE_FILENAME


def _migrations() -> list[tuple[str, str]]:
    package = resources.files("camera_count.db") / "migrations"
    found = [
        (item.name, item.read_text(encoding="utf-8"))
        for item in package.iterdir()
        if item.name.endswith(".sql")
    ]
    return sorted(found)


@dataclass(frozen=True, slots=True)
class StoredInspection:
    """A row from the inspections table, for listing past results."""

    id: int
    started_at_utc: str
    mode: str
    manufacturer: str | None
    model: str | None
    headline: str
    exact_count_found: bool


class Database:
    """A thin repository over SQLite. No ORM, no magic, no surprises."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_database_path()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
        finally:
            connection.close()

    def migrate(self) -> int:
        """Apply every migration that has not run yet. Returns the version."""
        with self.connect() as connection:
            for _name, sql in _migrations():
                connection.executescript(sql)
            current = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_version"
            ).fetchone()["version"]
            if current < SCHEMA_VERSION:
                connection.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
                )
            return SCHEMA_VERSION

    # -- writing --------------------------------------------------------------

    def save_inspection(
        self,
        result: InspectionResult,
        *,
        git_hash: str | None = None,
        seller_notes: str | None = None,
        buyer_notes: str | None = None,
    ) -> int:
        """Store one camera inspection and everything it produced."""
        self.migrate()
        now = datetime.now(UTC)
        device = result.device

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inspections (
                    started_at_utc, started_at_local, app_version, git_hash, mode,
                    manufacturer, model, serial, firmware, protocol,
                    usb_vendor_id, usb_product_id, usb_interfaces, adapter,
                    registry_model, headline, exact_count_found,
                    seller_notes, buyer_notes
                ) VALUES (?, ?, ?, ?, 'camera', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now.isoformat(),
                    now.astimezone().isoformat(),
                    __version__,
                    git_hash,
                    result.identity.manufacturer,
                    result.identity.model,
                    result.identity.serial,
                    result.identity.firmware,
                    result.identity.protocol.value,
                    device.vendor_id if device else None,
                    device.product_id if device else None,
                    device.describe_interfaces() if device else None,
                    result.adapter,
                    result.model.model if result.model else None,
                    result.headline,
                    1 if result.has_exact_count else 0,
                    seller_notes,
                    buyer_notes,
                ),
            )
            inspection_id = int(cursor.lastrowid or 0)
            self._save_counters(connection, inspection_id, result)
            self._save_transactions(connection, inspection_id, result.log)
            return inspection_id

    def save_image_inspection(
        self,
        analyses: Sequence[Any],
        *,
        git_hash: str | None = None,
        seller_notes: str | None = None,
        buyer_notes: str | None = None,
    ) -> int:
        """Store one image-mode inspection covering one or more files."""
        self.migrate()
        now = datetime.now(UTC)
        first = analyses[0] if analyses else None
        found = any(getattr(item, "has_exact_count", False) for item in analyses)

        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO inspections (
                    started_at_utc, started_at_local, app_version, git_hash, mode,
                    manufacturer, model, headline, exact_count_found,
                    registry_model, seller_notes, buyer_notes
                ) VALUES (?, ?, ?, ?, 'image', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now.isoformat(),
                    now.astimezone().isoformat(),
                    __version__,
                    git_hash,
                    getattr(first, "make", None),
                    getattr(first, "model", None),
                    "VERIFIED EXACT COUNT" if found else "EXACT COUNT UNAVAILABLE",
                    1 if found else 0,
                    getattr(getattr(first, "registry_model", None), "model", None),
                    seller_notes,
                    buyer_notes,
                ),
            )
            inspection_id = int(cursor.lastrowid or 0)

            for analysis in analyses:
                connection.execute(
                    """
                    INSERT INTO images (
                        inspection_id, path, file_name, size_bytes, sha256,
                        file_type, capture_date, is_original, originality_reason,
                        raw_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        inspection_id,
                        str(analysis.path),
                        analysis.path.name,
                        analysis.size_bytes,
                        analysis.sha256,
                        analysis.file_type,
                        analysis.capture_date,
                        1 if analysis.is_original else 0,
                        analysis.originality.reason if analysis.originality else None,
                        json.dumps(analysis.tags, default=str),
                    ),
                )
                self._save_slots(connection, inspection_id, analysis.counter_slots())
                for counter in analysis.non_authoritative:
                    connection.execute(
                        """
                        INSERT INTO non_authoritative_counters
                            (inspection_id, label, value, origin)
                        VALUES (?, ?, ?, ?)
                        """,
                        (inspection_id, counter.label, counter.value, counter.origin),
                    )
            return inspection_id

    def _save_counters(
        self, connection: sqlite3.Connection, inspection_id: int, result: InspectionResult
    ) -> None:
        self._save_slots(connection, inspection_id, result.counters)

    @staticmethod
    def _save_slots(
        connection: sqlite3.Connection, inspection_id: int, slots: Sequence[Any]
    ) -> None:
        for slot in slots:
            outcome = slot.result
            if isinstance(outcome, ShutterReading):
                connection.execute(
                    """
                    INSERT INTO shutter_readings (
                        inspection_id, count_type, available, value, source_id,
                        method_type, identifier, verification_status, citation,
                        transaction_ref
                    ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        inspection_id,
                        outcome.count_type.value,
                        outcome.value,
                        outcome.source_id,
                        outcome.source.method_type.value,
                        outcome.source.identifier,
                        outcome.source.verification_status.value,
                        outcome.source.citation.reference,
                        outcome.transaction_ref,
                    ),
                )
            elif isinstance(outcome, Unavailable):
                connection.execute(
                    """
                    INSERT INTO shutter_readings (
                        inspection_id, count_type, available, message, reason
                    ) VALUES (?, ?, 0, ?, ?)
                    """,
                    (inspection_id, slot.count_type.value, outcome.message, outcome.reason),
                )

    @staticmethod
    def _save_transactions(
        connection: sqlite3.Connection, inspection_id: int, log: TransactionLog
    ) -> None:
        for record in log.records:
            connection.execute(
                """
                INSERT INTO protocol_transactions (
                    inspection_id, reference, sequence, timestamp_utc, transport,
                    operation, opcode, parameters, response_name, response_code,
                    data_hex, duration_ms, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inspection_id,
                    record.reference,
                    record.index,
                    record.timestamp.isoformat(),
                    record.transport,
                    record.operation,
                    record.opcode,
                    json.dumps(list(record.parameters)),
                    record.response_name,
                    record.response_code,
                    record.data_hex(),
                    record.duration_ms,
                    record.note,
                ),
            )

    def record_verification(
        self,
        *,
        manufacturer: str,
        model: str,
        source_id: str,
        reading_before: int,
        presses: int,
        reading_after: int,
        firmware: str | None = None,
        tester: str | None = None,
        notes: str | None = None,
    ) -> int:
        """Record a human hardware test. The software never presses the shutter."""
        self.migrate()
        matched = 1 if reading_after - reading_before == presses else 0
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO verification_records (
                    manufacturer, model, firmware, source_id, reading_before,
                    presses, reading_after, matched, tested_at, tester, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manufacturer,
                    model,
                    firmware,
                    source_id,
                    reading_before,
                    presses,
                    reading_after,
                    matched,
                    datetime.now(UTC).isoformat(),
                    tester,
                    notes,
                ),
            )
            return int(cursor.lastrowid or 0)

    # -- reading --------------------------------------------------------------

    def recent_inspections(self, limit: int = 20) -> tuple[StoredInspection, ...]:
        self.migrate()
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, started_at_utc, mode, manufacturer, model, headline,
                       exact_count_found
                FROM inspections
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(
            StoredInspection(
                id=row["id"],
                started_at_utc=row["started_at_utc"],
                mode=row["mode"],
                manufacturer=row["manufacturer"],
                model=row["model"],
                headline=row["headline"],
                exact_count_found=bool(row["exact_count_found"]),
            )
            for row in rows
        )

    def readings_for(self, inspection_id: int) -> tuple[dict[str, Any], ...]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM shutter_readings WHERE inspection_id = ? ORDER BY id",
                (inspection_id,),
            ).fetchall()
        return tuple(dict(row) for row in rows)
