"""Smoke tests for the desktop window.

They run headless, and they check the things that matter about this particular
UI: that a count is shown with its source, that an unavailable count says so
plainly, and that nothing on screen ever hedges.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt", reason="pytest-qt is needed for the GUI tests")

from camera_count.core.enums import CitationKind, CountType, MethodType, VerificationStatus
from camera_count.core.messages import (
    EXACT_COUNT_UNAVAILABLE,
    EXACT_SHUTTER_COUNT_NOT_AVAILABLE,
    NOT_AVAILABLE,
    UNAVAILABLE_DISCLAIMER,
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

pytestmark = pytest.mark.gui

RECORD = SourceRecord(
    source_id="maker/body#0",
    manufacturer="Maker",
    model="Body",
    method_type=MethodType.MAKERNOTE_FIELD,
    identifier="Maker:ShutterCount",
    count_type=CountType.MECHANICAL,
    verification_status=VerificationStatus.DOCUMENTED,
    citation=Citation(kind=CitationKind.SOURCE_REF, reference="exiftool/Maker.pm:1"),
)


@pytest.fixture
def resolver():
    previous = set_source_resolver(
        type("R", (), {"resolve": lambda self, i: RECORD if i == RECORD.source_id else None})()
    )
    yield
    set_source_resolver(previous)


@pytest.fixture
def window(qtbot):
    from camera_count.gui.window import build_window

    made = build_window(watch_for_cameras=False)
    qtbot.addWidget(made)
    return made


def texts(widget) -> str:
    from PySide6.QtWidgets import QLabel

    return "\n".join(child.text() for child in widget.findChildren(QLabel) if child.text())


def test_window_opens_with_the_three_actions(window) -> None:
    assert window.inspect_button.text() == "Inspect camera"
    assert window.analyze_button.text() == "Analyse image"
    assert window.report_button.text() == "Create report"
    assert not window.report_button.isEnabled()


def test_identity_starts_as_not_available(window) -> None:
    for label in window.identity_fields.values():
        assert label.text() == NOT_AVAILABLE


def test_a_reading_is_shown_with_its_source(window, resolver) -> None:
    reading = ShutterReading.from_source(
        value=48_120, source_id=RECORD.source_id, transaction_ref="txn-0000"
    )
    result = InspectionResult(
        identity=CameraIdentity(manufacturer="Maker", model="Body", serial="SN1", firmware="1.40"),
        results=(reading,),
        counters=build_counter_slots([reading]),
        log=TransactionLog(),
    )

    window._on_inspection(result)

    shown = texts(window)
    assert "48120" in shown
    assert "VERIFIED EXACT COUNT" in window.headline_label.text()
    assert "exiftool/Maker.pm:1" in shown
    assert "documented" in shown
    assert window.identity_fields["Serial number"].text() == "SN1"
    assert window.report_button.isEnabled()


def test_an_unavailable_count_says_so_without_hedging(window) -> None:
    unavailable = Unavailable(
        message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason="No documented method."
    )
    result = InspectionResult(
        identity=CameraIdentity(manufacturer="Maker", model="Body"),
        results=(unavailable,),
        counters=build_counter_slots([unavailable], absent_reason="No documented method."),
        log=TransactionLog(),
    )

    window._on_inspection(result)

    shown = texts(window)
    assert window.headline_label.text() == EXACT_COUNT_UNAVAILABLE
    assert NOT_AVAILABLE in shown
    assert UNAVAILABLE_DISCLAIMER in shown


def test_no_hedging_vocabulary_appears_on_screen(window, resolver) -> None:
    reading = ShutterReading.from_source(value=1, source_id=RECORD.source_id)
    result = InspectionResult(
        identity=CameraIdentity(manufacturer="Maker", model="Body"),
        results=(reading,),
        counters=build_counter_slots([reading]),
        log=TransactionLog(),
    )

    window._on_inspection(result)

    shown = texts(window).lower()
    for term in ("approx", "probab", "confidence", "% sure"):
        assert term not in shown
    # "estimate" appears only inside the mandated disclaimer, which is not shown
    # when a count was found.
    assert "estimat" not in shown


def test_image_counters_are_shown_under_their_notice(window) -> None:
    unavailable = Unavailable(
        message=EXACT_SHUTTER_COUNT_NOT_AVAILABLE, reason="No documented method."
    )

    window._show_counters(
        build_counter_slots([unavailable], absent_reason="No documented method."),
        extra=(
            NonAuthoritativeCounter(label="FileNumber", value="1234", origin="Maker:FileNumber"),
        ),
    )

    shown = texts(window)
    assert "not an authoritative shutter-count source" in shown
    assert "FileNumber: 1234" in shown


def test_theme_toggles_between_light_and_dark(window) -> None:
    from camera_count.gui.theme import Theme

    assert window._theme is Theme.LIGHT
    window._toggle_theme()
    assert window._theme is Theme.DARK
    assert window.theme_button.text() == "Light theme"
    window._toggle_theme()
    assert window._theme is Theme.LIGHT


def test_actions_have_keyboard_shortcuts(window) -> None:
    shortcuts = {action.shortcut().toString() for action in window.actions()}

    assert {"F5", "Ctrl+O", "Ctrl+S", "Ctrl+T"} <= shortcuts


def test_creating_a_report_with_nothing_loaded_is_refused(window, monkeypatch) -> None:
    seen: list[str] = []
    monkeypatch.setattr(
        "camera_count.gui.window.QMessageBox.information",
        lambda *args, **kwargs: seen.append(args[1] if len(args) > 1 else ""),
    )

    window.create_report()

    assert seen
