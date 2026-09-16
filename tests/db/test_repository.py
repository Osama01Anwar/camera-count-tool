"""The database refuses an unsourced count, in SQL, not just in Python."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from camera_count.core.enums import CitationKind, CountType, MethodType, VerificationStatus
from camera_count.core.messages import EXACT_SHUTTER_COUNT_NOT_AVAILABLE
from camera_count.core.models import (
    CameraIdentity,
    ShutterReading,
    Unavailable,
    build_counter_slots,
)
from camera_count.core.sources import Citation, SourceRecord, set_source_resolver
from camera_count.db import Database
from camera_count.diagnostics.log import TransactionLog
from camera_count.inspection import InspectionResult

RECORD = SourceRecord(
    source_id="maker/body#0",
    manufacturer="Maker",
    model="Body",
    method_type=MethodType.PTP_PROPERTY,
    identifier="0xD1A3",
    count_type=CountType.MECHANICAL,
    verification_status=VerificationStatus.DOCUMENTED,
    citation=Citation(kind=CitationKind.SOURCE_REF, reference="tests/db:1"),
)


@pytest.fixture
def database(tmp_path: Path) -> Database:
    db = Database(tmp_path / "test.sqlite")
    db.migrate()
    return db


@pytest.fixture
def resolver():
    previous = set_source_resolver(
        type("R", (), {"resolve": lambda self, i: RECORD if i == RECORD.source_id else None})()
    )
    yield
    set_source_resolver(previous)


def test_migration_is_idempotent(database: Database) -> None:
    assert database.migrate() == database.migrate()


def test_saving_an_inspection_stores_its_reading(database: Database, resolver) -> None:
    reading = ShutterReading.from_source(
        value=48_120, source_id=RECORD.source_id, transaction_ref="txn-0000"
    )
    log = TransactionLog(transport="test")
    log.record(operation="GET_DEVICE_PROP_VALUE", opcode=0x1015, response_name="OK")
    result = InspectionResult(
        identity=CameraIdentity(manufacturer="Maker", model="Body", serial="SN1"),
        adapter="maker",
        results=(reading,),
        counters=build_counter_slots([reading]),
        log=log,
    )

    inspection_id = database.save_inspection(result)

    rows = database.readings_for(inspection_id)
    available = [row for row in rows if row["available"]]
    assert len(available) == 1
    assert available[0]["value"] == 48_120
    assert available[0]["citation"] == "tests/db:1"
    assert available[0]["verification_status"] == "documented"
    assert len(rows) == len(CountType)


def test_unavailable_counters_are_stored_with_their_reason(database: Database) -> None:
    unavailable = Unavailable(
        message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason="No documented method."
    )
    result = InspectionResult(
        identity=CameraIdentity(manufacturer="Maker", model="Body"),
        results=(unavailable,),
        counters=build_counter_slots([unavailable], absent_reason="No documented method."),
        log=TransactionLog(),
    )

    inspection_id = database.save_inspection(result)

    rows = database.readings_for(inspection_id)
    assert all(row["value"] is None for row in rows)
    assert all(row["reason"] for row in rows)


def test_the_schema_refuses_a_count_without_a_source(database: Database) -> None:
    """The guard is in the database too, not only in the application."""
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO inspections (
                started_at_utc, started_at_local, app_version, mode, headline,
                exact_count_found
            ) VALUES ('t', 't', '0', 'camera', 'x', 1)
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO shutter_readings (inspection_id, count_type, available, value)
                VALUES (1, 'mechanical', 1, 48120)
                """
            )


def test_the_schema_refuses_an_unverified_source(database: Database) -> None:
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO inspections (
                started_at_utc, started_at_local, app_version, mode, headline,
                exact_count_found
            ) VALUES ('t', 't', '0', 'camera', 'x', 1)
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO shutter_readings (
                    inspection_id, count_type, available, value, source_id,
                    citation, verification_status
                ) VALUES (1, 'mechanical', 1, 48120, 's', 'c', 'unverified')
                """
            )


def test_a_hardware_test_must_add_up(database: Database) -> None:
    good = database.record_verification(
        manufacturer="Maker",
        model="Body",
        source_id=RECORD.source_id,
        reading_before=100,
        presses=10,
        reading_after=110,
    )
    assert good > 0

    with database.connect() as connection:
        row = connection.execute(
            "SELECT matched FROM verification_records WHERE id = ?", (good,)
        ).fetchone()
        assert row["matched"] == 1

    mismatch = database.record_verification(
        manufacturer="Maker",
        model="Body",
        source_id=RECORD.source_id,
        reading_before=100,
        presses=10,
        reading_after=115,
    )
    with database.connect() as connection:
        row = connection.execute(
            "SELECT matched FROM verification_records WHERE id = ?", (mismatch,)
        ).fetchone()
        assert row["matched"] == 0


def test_transactions_are_stored_for_traceability(database: Database, resolver) -> None:
    log = TransactionLog(transport="test")
    log.record(operation="GET_DEVICE_INFO", opcode=0x1001, response_name="OK", data=b"\x01\x02")
    result = InspectionResult(identity=CameraIdentity(manufacturer="Maker", model="Body"), log=log)

    inspection_id = database.save_inspection(result)

    with database.connect() as connection:
        rows = connection.execute(
            "SELECT * FROM protocol_transactions WHERE inspection_id = ?", (inspection_id,)
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["operation"] == "GET_DEVICE_INFO"
    assert rows[0]["data_hex"] == "0102"


def test_recent_inspections_are_listed_newest_first(database: Database) -> None:
    for index in range(3):
        database.save_inspection(
            InspectionResult(
                identity=CameraIdentity(manufacturer="Maker", model=f"Body {index}"),
                log=TransactionLog(),
            )
        )

    recent = database.recent_inspections(limit=2)

    assert len(recent) == 2
    assert recent[0].model == "Body 2"
    assert recent[0].exact_count_found is False
