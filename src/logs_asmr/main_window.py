"""Main application window — log workspace with source tree, action bar, and log view."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QByteArray, Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from logs_asmr.audio.audio_manager import AudioManager
from logs_asmr.audio.state_machine import AudioStateMachine
from logs_asmr.connectors import registry
from logs_asmr.connectors.base import TailWorker
from logs_asmr.constants import (
    DEFAULT_SPLITTER_LEFT,
    DEFAULT_SPLITTER_RIGHT,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
)
from logs_asmr.streaming.event_processor import EventProcessor
from logs_asmr.streaming.ring_buffer import RingBuffer
from logs_asmr.ui.action_bar import ActionBar
from logs_asmr.ui.filter_drawer import FilterDrawer
from logs_asmr.ui.log_view import LogView
from logs_asmr.ui.source_panel import SourcePanel
from logs_asmr.ui.status_bar import StatusBarManager

if TYPE_CHECKING:
    from logs_asmr.db.database import Database
    from logs_asmr.models.filter_state import FilterState
    from logs_asmr.models.log_event import LogEvent
    from logs_asmr.models.source import Source
    from logs_asmr.testing.fake_tail import FakeTailWorker

logger = logging.getLogger("logs_asmr.main_window")


class MainWindow(QMainWindow):
    def __init__(self, db: Database | None = None, fake: bool = False) -> None:
        super().__init__()
        self._db = db
        self._fake = fake
        self._fake_worker: FakeTailWorker | None = None
        self._tail_worker: TailWorker | None = None
        self._ring_buffer = RingBuffer()
        self._processor = EventProcessor(self._ring_buffer, self)

        # Audio
        self._audio_sm = AudioStateMachine(self)
        self._audio_mgr = AudioManager(self._audio_sm, self)

        self.setWindowTitle("Logs ASMR")
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        self._setup_action_bar()
        self._setup_central()
        self._setup_filter_drawer()
        self._setup_status_bar()
        self._connect_signals()
        self._setup_keyboard_shortcuts()
        self._detect_night_mode()
        self._restore_state()

        logger.info("Main window initialized (fake=%s)", fake)

        # Start after event loop begins
        QTimer.singleShot(0, self._init_streaming)

    def _setup_action_bar(self) -> None:
        self._action_bar = ActionBar()

    def _setup_central(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._action_bar)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        self._source_panel = SourcePanel(db=self._db)
        self._splitter.addWidget(self._source_panel)

        self._log_view = LogView()
        self._splitter.addWidget(self._log_view)

        self._splitter.setSizes([DEFAULT_SPLITTER_LEFT, DEFAULT_SPLITTER_RIGHT])
        layout.addWidget(self._splitter)

        self.setCentralWidget(central)

    def _setup_filter_drawer(self) -> None:
        self._filter_drawer = FilterDrawer(self, db=self._db)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._filter_drawer)
        self._filter_drawer.hide()

    def _setup_status_bar(self) -> None:
        self._status_mgr = StatusBarManager(self.statusBar())

    def _connect_signals(self) -> None:
        # Action bar
        self._action_bar.tail_toggled.connect(self._on_tail_toggled)
        self._action_bar.clear_clicked.connect(self._on_clear)
        self._action_bar.catch_up_clicked.connect(self._on_catch_up)
        self._action_bar.filter_drawer_toggled.connect(self._on_filter_drawer_toggled)
        self._action_bar.mute_toggled.connect(self._on_mute_toggled)
        self._action_bar.settings_clicked.connect(self._on_settings_clicked)

        # Source panel
        self._source_panel.source_selected.connect(self._on_source_selected)

        # Filter drawer
        self._filter_drawer.filter_changed.connect(self._on_filter_changed)
        self._filter_drawer.visibilityChanged.connect(
            lambda vis: self._action_bar.set_filter_checked(vis)
        )

        # Event processor -> log view
        self._processor.filtered_batch.connect(self._on_filtered_batch)
        self._processor.refiltered_all.connect(self._on_refiltered_all)
        self._processor.drop_count_updated.connect(self._on_drop_count_updated)
        self._processor.event_rate_updated.connect(self._status_mgr.set_event_rate)
        self._processor.components_discovered.connect(self._filter_drawer.add_components)

        # Audio trigger
        self._processor.error_batch.connect(self._audio_sm.on_error_batch)

    def _setup_keyboard_shortcuts(self) -> None:
        # M = mute toggle
        mute_action = QAction("Toggle Mute", self)
        mute_action.setShortcut(QKeySequence("M"))
        mute_action.triggered.connect(self._action_bar._on_mute_clicked)
        self.addAction(mute_action)

        # Space = tail/pause
        tail_action = QAction("Toggle Tail", self)
        tail_action.setShortcut(QKeySequence("Space"))
        tail_action.triggered.connect(self._action_bar._on_tail_clicked)
        self.addAction(tail_action)

        # Ctrl+L = clear
        clear_action = QAction("Clear", self)
        clear_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_action.triggered.connect(self._on_clear)
        self.addAction(clear_action)

        # Ctrl+F = focus include filter
        filter_action = QAction("Focus Filter", self)
        filter_action.setShortcut(QKeySequence("Ctrl+F"))
        filter_action.triggered.connect(self._focus_filter)
        self.addAction(filter_action)

        # Escape = close filter drawer
        esc_action = QAction("Close Filter", self)
        esc_action.setShortcut(QKeySequence("Escape"))
        esc_action.triggered.connect(lambda: self._filter_drawer.hide())
        self.addAction(esc_action)

    def _detect_night_mode(self) -> None:
        """Detect system dark mode and adjust audio volume."""
        from PyQt6.QtWidgets import QApplication

        palette = QApplication.palette()
        bg = palette.color(palette.ColorRole.Window)
        # If background is dark, consider it night mode
        is_dark = bg.lightness() < 128
        self._audio_mgr.set_night_mode(is_dark)

    def _focus_filter(self) -> None:
        if not self._filter_drawer.isVisible():
            self._filter_drawer.show()
            self._action_bar.set_filter_checked(True)
        self._filter_drawer._include_input.setFocus()

    def _init_streaming(self) -> None:
        self._processor.start()

        if self._fake:
            self._start_fake_tail()
        else:
            self._source_panel.populate()

    def _start_fake_tail(self) -> None:
        from logs_asmr.testing.fake_tail import FakeTailWorker

        self._fake_worker = FakeTailWorker(self._ring_buffer, parent=self)
        self._fake_worker.signals.status_changed.connect(self._on_status_changed)
        self._fake_worker.start()
        self._status_mgr.set_status("Streaming (fake)")
        self._audio_sm.set_streaming(True)
        logger.info("Fake tail worker started")

    # --- Source selection ---

    def _on_source_selected(self, source: Source) -> None:
        self._stop_tail()
        self._on_clear()

        self._status_mgr.set_status(f"Connecting to {source.display_name}...")
        self._save_recent_source(source)
        logger.info("Source selected: %s", source)

        plugin = registry.get_plugin(source.connector)
        if not plugin:
            self._on_error(f"Connector '{source.connector}' not available")
            return

        self._tail_worker = plugin.worker_class(
            self._ring_buffer, source, parent=self
        )
        self._tail_worker.signals.status_changed.connect(self._on_status_changed)
        self._tail_worker.signals.error_occurred.connect(self._on_error)
        self._tail_worker.start()

    def _stop_tail(self) -> None:
        if self._tail_worker is not None:
            self._tail_worker.stop()
            if not self._tail_worker.wait(3000):
                logger.warning("Tail worker did not stop within timeout, forcing termination")
                self._tail_worker.terminate()
                self._tail_worker.wait(1000)
            self._tail_worker.deleteLater()
            self._tail_worker = None
        self._audio_sm.set_streaming(False)

    # --- Action handlers ---

    def _on_tail_toggled(self, is_live: bool) -> None:
        self._processor.set_paused(not is_live)
        self._log_view.set_auto_scroll(is_live)

    def _on_clear(self) -> None:
        self._log_view.clear()
        self._processor.clear()
        self._ring_buffer.reset_drop_count()
        self._status_mgr.set_drop_count(0)
        self._action_bar.set_status("connected")

    def _on_catch_up(self) -> None:
        self._ring_buffer.clear()
        self._on_clear()

    def _on_drop_count_updated(self, count: int) -> None:
        self._status_mgr.set_drop_count(count)
        if count > 0:
            self._action_bar.set_status("dropping")

    def _on_filter_drawer_toggled(self, visible: bool) -> None:
        self._filter_drawer.setVisible(visible)

    def _on_filter_changed(self, state: FilterState) -> None:
        self._processor.update_filter(state)

    def _on_mute_toggled(self, is_muted: bool) -> None:
        self._audio_sm.set_muted(is_muted)

    def _on_filtered_batch(self, events: list[LogEvent]) -> None:
        self._log_view.append_events(events)

    def _on_refiltered_all(self, events: list[LogEvent]) -> None:
        self._log_view.replace_all(events)

    def _on_status_changed(self, status: str) -> None:
        self._action_bar.set_status(status)
        self._status_mgr.set_status(status.title())
        if status == "connected":
            self._audio_sm.set_streaming(True)
        elif status == "disconnected":
            self._audio_sm.set_streaming(False)

    def _on_error(self, message: str) -> None:
        self._status_mgr.set_status(f"Error: {message}")
        logger.error("Tail error: %s", message)
        QMessageBox.warning(self, "Connection Error", message)

    def _on_settings_clicked(self) -> None:
        from logs_asmr.ui.settings_dialog import SettingsDialog

        dialog = SettingsDialog(audio_mgr=self._audio_mgr, db=self._db, parent=self)
        dialog.settings_changed.connect(self._source_panel.reload_browsers)
        dialog.exec()

    # --- Recent sources ---

    def _save_recent_source(self, source: Source) -> None:
        if self._db is None:
            return
        self._db.execute(
            "INSERT OR REPLACE INTO recent_sources "
            "(connector, params_json, label, used_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (source.connector, json.dumps(source.params, sort_keys=True), source.label),
        )

    # --- Window state save/restore ---

    def _save_state(self) -> None:
        if self._db is None:
            return
        from logs_asmr.db.database import set_pref

        set_pref(self._db, "window_geometry", self.saveGeometry().toBase64().data().decode())
        set_pref(self._db, "window_state", self.saveState().toBase64().data().decode())
        set_pref(
            self._db,
            "splitter_state",
            self._splitter.saveState().toBase64().data().decode(),
        )
        set_pref(
            self._db,
            "filter_drawer_visible",
            "true" if self._filter_drawer.isVisible() else "false",
        )
        set_pref(self._db, "audio.volume", str(int(self._audio_mgr.volume * 100)))

    def _restore_state(self) -> None:
        if self._db is None:
            return
        from logs_asmr.db.database import get_bool_pref, get_int_pref, get_pref

        geom = get_pref(self._db, "window_geometry")
        if geom:
            self.restoreGeometry(QByteArray.fromBase64(geom.encode()))

        state = get_pref(self._db, "window_state")
        if state:
            self.restoreState(QByteArray.fromBase64(state.encode()))

        splitter = get_pref(self._db, "splitter_state")
        if splitter:
            self._splitter.restoreState(QByteArray.fromBase64(splitter.encode()))

        dock_vis = get_bool_pref(self._db, "filter_drawer_visible", default=False)
        self._filter_drawer.setVisible(dock_vis)
        self._action_bar.set_filter_checked(dock_vis)

        volume = get_int_pref(self._db, "audio.volume", default=-1)
        if volume >= 0:
            self._audio_mgr.set_volume(volume / 100.0)

    def closeEvent(self, event) -> None:
        self._save_state()
        self._stop_tail()
        if self._fake_worker is not None:
            self._fake_worker.stop()
            self._fake_worker.wait(2000)
        self._processor.stop()
        super().closeEvent(event)
