"""The main window.

One screen, three things on it: what is connected, what the counters say, and
what you can do about it. No charts, no gauges, no progress theatre, no
percentages. The number and where it came from are the whole point, so they get
the space.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from camera_count import __version__
from camera_count.core.messages import (
    EXACT_COUNT_UNAVAILABLE,
    IMAGE_COUNTER_NOTICE,
    NOT_AVAILABLE,
    READ_ONLY_NOTICE,
    UNAVAILABLE_DISCLAIMER,
)
from camera_count.core.models import CameraIdentity, ShutterReading
from camera_count.gui.theme import Theme, palette_for
from camera_count.gui.workers import Task, analyze_task, detect_task, inspect_task

HOTPLUG_INTERVAL_MS = 4000

COUNTER_LABELS = {
    "mechanical": "Mechanical shutter",
    "electronic": "Electronic shutter",
    "efc": "Electronic first curtain",
    "total_releases": "Total releases",
}

IMAGE_FILTER = (
    "Camera files (*.jpg *.jpeg *.heic *.heif *.tif *.tiff *.dng *.cr2 *.cr3 *.crw "
    "*.nef *.nrw *.arw *.sr2 *.raf *.rw2 *.orf *.ori *.pef *.srw *.3fr *.iiq *.x3f);;"
    "All files (*.*)"
)


def panel(title: str) -> tuple[QFrame, QVBoxLayout]:
    """A titled panel with its own content layout."""
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    heading = QLabel(title.upper())
    heading.setObjectName("sectionHeading")
    layout.addWidget(heading)
    return frame, layout


class MainWindow(QMainWindow):
    """Camera Count Tool."""

    def __init__(self, *, watch_for_cameras: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("Camera Count Tool")
        self.resize(880, 760)
        self._theme = Theme.LIGHT
        self._task: Task | None = None
        self._watcher: Task | None = None
        self._last_result: Any = None
        self._last_analyses: tuple[Any, ...] = ()

        self._build()
        self._apply_theme()
        if watch_for_cameras:
            self._start_hotplug_watch()
        else:
            self._set_connection("Camera watching is off.")

    # -- construction ---------------------------------------------------------

    def _build(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(16)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_status_panel())
        outer.addWidget(self._build_count_panel(), stretch=1)
        outer.addLayout(self._build_actions())

        notice = QLabel(READ_ONLY_NOTICE)
        notice.setObjectName("meta")
        notice.setWordWrap(True)
        outer.addWidget(notice)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready.")
        self._build_shortcuts()

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        column = QVBoxLayout()
        title = QLabel("Camera Count Tool")
        title.setObjectName("title")
        subtitle = QLabel("Exact shutter count from an authoritative source, or nothing at all.")
        subtitle.setObjectName("subtitle")
        column.addWidget(title)
        column.addWidget(subtitle)
        row.addLayout(column)
        row.addStretch(1)

        self.theme_button = QPushButton("Dark theme")
        self.theme_button.setToolTip("Switch between the light and dark themes (Ctrl+T)")
        self.theme_button.clicked.connect(self._toggle_theme)
        row.addWidget(self.theme_button)
        return row

    def _build_status_panel(self) -> QFrame:
        frame, layout = panel("Camera status")
        self.connection_label = QLabel("Checking for a connected camera...")
        self.connection_label.setObjectName("fieldValue")
        self.connection_label.setWordWrap(True)
        layout.addWidget(self.connection_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        self.identity_fields: dict[str, QLabel] = {}
        for row, name in enumerate(
            ("Manufacturer", "Model", "Serial number", "Firmware", "Protocol")
        ):
            label = QLabel(name)
            label.setObjectName("fieldLabel")
            value = QLabel(NOT_AVAILABLE)
            value.setObjectName("fieldValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
            self.identity_fields[name] = value
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return frame

    def _build_count_panel(self) -> QWidget:
        frame, layout = panel("Exact shutter count")

        self.headline_label = QLabel(EXACT_COUNT_UNAVAILABLE)
        self.headline_label.setObjectName("headline")
        layout.addWidget(self.headline_label)

        self.counters_host = QWidget()
        self.counters_layout = QVBoxLayout(self.counters_host)
        self.counters_layout.setContentsMargins(0, 4, 0, 0)
        self.counters_layout.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.counters_host)
        layout.addWidget(scroll, stretch=1)

        self._show_placeholder()
        return frame

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        self.inspect_button = QPushButton("Inspect camera")
        self.inspect_button.setToolTip("Read the connected camera (F5)")
        self.inspect_button.clicked.connect(self.inspect_camera)

        self.analyze_button = QPushButton("Analyse image")
        self.analyze_button.setToolTip("Read an original camera file (Ctrl+O)")
        self.analyze_button.clicked.connect(self.analyze_image)

        self.report_button = QPushButton("Create report")
        self.report_button.setToolTip("Write a Used Camera Inspection Report (Ctrl+S)")
        self.report_button.clicked.connect(self.create_report)
        self.report_button.setEnabled(False)

        for button in (self.inspect_button, self.analyze_button, self.report_button):
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.addWidget(button)
        return row

    def _build_shortcuts(self) -> None:
        for shortcut, slot in (
            ("F5", self.inspect_camera),
            ("Ctrl+O", self.analyze_image),
            ("Ctrl+S", self.create_report),
            ("Ctrl+T", self._toggle_theme),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(slot)
            self.addAction(action)

    # -- theme ----------------------------------------------------------------

    def _apply_theme(self) -> None:
        palette = palette_for(self._theme)
        self.setStyleSheet(palette.stylesheet())
        self.theme_button.setText("Dark theme" if self._theme is Theme.LIGHT else "Light theme")

    def _toggle_theme(self) -> None:
        self._theme = Theme.DARK if self._theme is Theme.LIGHT else Theme.LIGHT
        self._apply_theme()
        self._refresh_headline_style()

    # -- hot plug -------------------------------------------------------------

    def _start_hotplug_watch(self) -> None:
        self._hotplug = QTimer(self)
        self._hotplug.setInterval(HOTPLUG_INTERVAL_MS)
        self._hotplug.timeout.connect(self._check_connection)
        self._hotplug.start()
        self._check_connection()

    def _check_connection(self) -> None:
        if self._watcher is not None and self._watcher.isRunning():
            return
        self._watcher = detect_task(self)
        self._watcher.succeeded.connect(self._on_detection)
        self._watcher.failed.connect(lambda message: self._set_connection(message))
        self._watcher.start()

    def _on_detection(self, report: Any) -> None:
        if not report.cameras:
            self._set_connection(
                "No camera connected. Switch the camera on, use a data cable, and "
                "set its USB mode to PTP / PC Remote / MTP."
            )
            self.inspect_button.setEnabled(False)
            return

        camera = report.cameras[0]
        if camera.claimed_by:
            self._set_connection(f"Camera found, but it is held by {camera.claimed_by}")
            self.inspect_button.setEnabled(False)
            return

        self._set_connection(
            f"Connected: {camera.display_product()} ({camera.usb_ids}) via {camera.backend}"
        )
        self.inspect_button.setEnabled(True)

    def _set_connection(self, text: str) -> None:
        self.connection_label.setText(text)

    # -- actions --------------------------------------------------------------

    def inspect_camera(self) -> None:
        if self._busy():
            return
        self._begin("Reading the camera...")
        self._task = inspect_task(self)
        self._task.succeeded.connect(self._on_inspection)
        self._task.failed.connect(self._on_failure)
        self._task.start()

    def analyze_image(self) -> None:
        if self._busy():
            return
        names, _ = QFileDialog.getOpenFileNames(
            self, "Choose original camera files", "", IMAGE_FILTER
        )
        if not names:
            return
        self._begin("Reading the file...")
        self._task = analyze_task([Path(name) for name in names], self)
        self._task.succeeded.connect(self._on_analyses)
        self._task.failed.connect(self._on_failure)
        self._task.start()

    def create_report(self) -> None:
        if self._last_result is None and not self._last_analyses:
            QMessageBox.information(
                self,
                "Nothing to report yet",
                "Inspect a camera or analyse an image first.",
            )
            return

        name, _ = QFileDialog.getSaveFileName(
            self,
            "Save report",
            "camera-count-report.html",
            "HTML report (*.html);;PDF report (*.pdf);;JSON report (*.json)",
        )
        if not name:
            return

        from camera_count.report import (  # noqa: PLC0415
            ReportFormat,
            from_image_analyses,
            from_inspection,
        )
        from camera_count.report.builder import write_report  # noqa: PLC0415

        destination = Path(name)
        suffix = destination.suffix.lower().lstrip(".")
        try:
            chosen = ReportFormat(suffix)
        except ValueError:
            chosen = ReportFormat.HTML
            destination = destination.with_suffix(".html")

        data = (
            from_inspection(self._last_result)
            if self._last_result is not None
            else from_image_analyses(list(self._last_analyses))
        )
        try:
            written, digest = write_report(data, destination, chosen)
        except Exception as exc:  # noqa: BLE001 - report the failure, do not crash
            QMessageBox.warning(self, "The report could not be written", str(exc))
            return

        self.statusBar().showMessage(f"Wrote {written}  -  content SHA-256 {digest}")

    # -- results --------------------------------------------------------------

    def _busy(self) -> bool:
        return self._task is not None and self._task.isRunning()

    def _begin(self, message: str) -> None:
        self.statusBar().showMessage(message)
        for button in (self.inspect_button, self.analyze_button):
            button.setEnabled(False)

    def _end(self, message: str) -> None:
        self.statusBar().showMessage(message)
        self.analyze_button.setEnabled(True)
        self.inspect_button.setEnabled(True)

    def _on_failure(self, message: str) -> None:
        self._end("Something went wrong.")
        QMessageBox.warning(self, "Camera Count Tool", message)

    def _on_inspection(self, result: Any) -> None:
        self._last_result = result
        self._last_analyses = ()
        self._show_identity(result.identity)
        self._show_counters(result.counters, failure=result.failure)
        self.report_button.setEnabled(True)
        self._end(f"{result.headline}  -  {len(result.log)} protocol transactions recorded.")

    def _on_analyses(self, analyses: Any) -> None:
        self._last_analyses = tuple(analyses)
        self._last_result = None
        first = self._last_analyses[0] if self._last_analyses else None
        if first is None:
            self._end("No file was read.")
            return

        self._show_identity(CameraIdentity(manufacturer=first.make, model=first.model))
        slots: list[Any] = []
        for analysis in self._last_analyses:
            slots.extend(analysis.counter_slots())
        self._show_counters(
            tuple(slots),
            failure=first.blocking_failure,
            extra=first.non_authoritative,
        )
        self.report_button.setEnabled(True)
        self._end(f"Read {len(self._last_analyses)} file(s).")

    def _show_identity(self, identity: CameraIdentity) -> None:
        self.identity_fields["Manufacturer"].setText(identity.display_manufacturer())
        self.identity_fields["Model"].setText(identity.display_model())
        self.identity_fields["Serial number"].setText(identity.display_serial())
        self.identity_fields["Firmware"].setText(identity.display_firmware())
        self.identity_fields["Protocol"].setText(identity.protocol.value)

    def _clear_counters(self) -> None:
        while self.counters_layout.count():
            item = self.counters_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_placeholder(self) -> None:
        self._clear_counters()
        message = QLabel(
            "Connect a camera and choose Inspect camera, or choose Analyse image "
            "to read an original file."
        )
        message.setObjectName("meta")
        message.setWordWrap(True)
        self.counters_layout.addWidget(message)
        self.counters_layout.addStretch(1)

    def _show_counters(
        self, slots: tuple[Any, ...], *, failure: Any = None, extra: tuple[Any, ...] = ()
    ) -> None:
        self._clear_counters()

        found = any(isinstance(slot.result, ShutterReading) for slot in slots)
        self.headline_label.setText("VERIFIED EXACT COUNT" if found else EXACT_COUNT_UNAVAILABLE)
        self._refresh_headline_style(found)

        if failure is not None:
            banner = QLabel(f"{failure.message}\n{failure.reason}")
            banner.setObjectName("meta")
            banner.setWordWrap(True)
            self.counters_layout.addWidget(banner)

        # A counter that has a value comes first. The number someone is buying a
        # camera on should not be below the fold under three empty slots.
        ordered = sorted(
            slots, key=lambda slot: 0 if isinstance(slot.result, ShutterReading) else 1
        )
        for slot in ordered:
            self.counters_layout.addWidget(self._counter_widget(slot))

        if not found:
            disclaimer = QLabel(UNAVAILABLE_DISCLAIMER)
            disclaimer.setObjectName("meta")
            self.counters_layout.addWidget(disclaimer)

        if extra:
            notice = QLabel(IMAGE_COUNTER_NOTICE)
            notice.setObjectName("meta")
            notice.setWordWrap(True)
            self.counters_layout.addWidget(notice)
            for counter in extra:
                item = QLabel(f"{counter.label}: {counter.value}  (from {counter.origin})")
                item.setObjectName("meta")
                self.counters_layout.addWidget(item)

        self.counters_layout.addStretch(1)

    def _counter_widget(self, slot: Any) -> QWidget:
        """One counter.

        A counter with a value gets the large type and its full provenance. An
        empty one stays compact: it still says NOT AVAILABLE and why, but it
        does not shout as loudly as a real number.
        """
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label = COUNTER_LABELS.get(slot.count_type.value, slot.count_type.value)
        outcome = slot.result

        if isinstance(outcome, ShutterReading):
            name = QLabel(label)
            name.setObjectName("fieldLabel")
            layout.addWidget(name)

            value = QLabel(str(outcome.value))
            value.setObjectName("countValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(value)

            meta = QLabel(
                f"Source: {outcome.source.method_type.value} {outcome.source.identifier}\n"
                f"Status: {outcome.source.verification_status.value}\n"
                f"Cited: {outcome.source.citation.display()}"
            )
        else:
            headline = QLabel(f"{label}: {NOT_AVAILABLE}")
            headline.setObjectName("fieldValue")
            layout.addWidget(headline)
            meta = QLabel(outcome.reason)

        meta.setObjectName("meta")
        meta.setWordWrap(True)
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(meta)
        return holder

    def _refresh_headline_style(self, found: bool | None = None) -> None:
        if found is None:
            found = self.headline_label.text() == "VERIFIED EXACT COUNT"
        self.headline_label.setObjectName("headlineFound" if found else "headlineAbsent")
        palette = palette_for(self._theme)
        self.headline_label.setStyleSheet(
            f"font-size: 17px; font-weight: 700; letter-spacing: 0.5px; color: "
            f"{palette.found if found else palette.absent};"
        )


def build_window(*, watch_for_cameras: bool = True) -> MainWindow:
    """Create the window. Split out so tests can build it without running the app."""
    window = MainWindow(watch_for_cameras=watch_for_cameras)
    window.setWindowTitle(f"Camera Count Tool {__version__}")
    if QGuiApplication.instance() is not None:
        window.setWindowFlag(Qt.WindowType.Window, True)
    return window
