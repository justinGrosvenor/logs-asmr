"""Settings dialog with per-connector settings and audio controls."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from logs_asmr.audio.audio_manager import DEFAULT_FILES, SOUND_SLOTS
from logs_asmr.connectors import registry
from logs_asmr.ui import theme

if TYPE_CHECKING:
    from logs_asmr.audio.audio_manager import AudioManager
    from logs_asmr.db.database import Database

logger = logging.getLogger("logs_asmr.settings_dialog")

_SLOT_LABELS = ["Healthy", "Warning", "Alarm", "Noise Floor"]
_SOUND_FILTER = "Audio Files (*.wav *.mp3 *.opus)"


class AudioTab(QWidget):
    """Tab for audio volume and custom sound controls."""

    def __init__(
        self,
        audio_mgr: AudioManager | None = None,
        db: Database | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._audio_mgr = audio_mgr
        self._db = db
        self._filename_labels: list[QLabel] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- Volume ---
        vol_form = QFormLayout()
        vol_row = QHBoxLayout()
        self._volume_slider = QSlider()
        self._volume_slider.setOrientation(self._horizontal())
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(int((audio_mgr.volume if audio_mgr else 0.33) * 100))
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_row.addWidget(self._volume_slider)
        self._volume_label = QLabel(f"{self._volume_slider.value()}%")
        self._volume_label.setFixedWidth(36)
        vol_row.addWidget(self._volume_label)
        vol_form.addRow("Volume:", vol_row)
        layout.addLayout(vol_form)

        # --- Sound slots ---
        group = QGroupBox("Sounds")
        grid = QGridLayout(group)
        grid.setColumnStretch(1, 1)

        for i, label_text in enumerate(_SLOT_LABELS):
            label = QLabel(label_text)
            grid.addWidget(label, i, 0)

            filename = self._current_filename(i)
            file_label = QLabel(filename)
            file_label.setStyleSheet(theme.subtext_style())
            self._filename_labels.append(file_label)
            grid.addWidget(file_label, i, 1)

            browse_btn = QPushButton("Browse...")
            browse_btn.setFixedWidth(80)
            browse_btn.clicked.connect(lambda checked, idx=i: self._on_browse(idx))
            grid.addWidget(browse_btn, i, 2)

            reset_btn = QPushButton("Reset")
            reset_btn.setFixedWidth(60)
            reset_btn.clicked.connect(lambda checked, idx=i: self._on_reset(idx))
            grid.addWidget(reset_btn, i, 3)

        layout.addWidget(group)

        # --- Description ---
        desc = QLabel(
            "Audio levels crossfade automatically based on log severity:\n"
            "  Healthy = ocean waves  |  Warning = rain + thunder  |  Alarm = thunderstorm"
        )
        layout.addWidget(desc)
        layout.addStretch()

    def _current_filename(self, slot_index: int) -> str:
        if self._audio_mgr:
            return self._audio_mgr.current_filename(slot_index)
        return DEFAULT_FILES[slot_index]

    @staticmethod
    def _horizontal():  # noqa: ANN205
        from PyQt6.QtCore import Qt

        return Qt.Orientation.Horizontal

    def _on_volume_changed(self, value: int) -> None:
        self._volume_label.setText(f"{value}%")
        if self._audio_mgr:
            self._audio_mgr.set_volume(value / 100.0)
        if self._db:
            from logs_asmr.db.database import set_pref

            set_pref(self._db, "audio.volume", str(value))

    def _on_browse(self, slot_index: int) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Sound File", "", _SOUND_FILTER)
        if not path:
            return

        if self._audio_mgr:
            self._audio_mgr.set_sound(slot_index, path)

        self._filename_labels[slot_index].setText(self._current_filename(slot_index))
        logger.info("Custom sound selected for %s: %s", SOUND_SLOTS[slot_index], path)

    def _on_reset(self, slot_index: int) -> None:
        if self._audio_mgr:
            self._audio_mgr.reset_sound(slot_index)

        self._filename_labels[slot_index].setText(DEFAULT_FILES[slot_index])
        logger.info("Sound reset to default for %s", SOUND_SLOTS[slot_index])


class SettingsDialog(QDialog):
    """Application settings dialog with tabs."""

    settings_changed = pyqtSignal()

    def __init__(
        self,
        audio_mgr: AudioManager | None = None,
        db: Database | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Connectors tab — sub-tabs for each plugin with settings
        connector_tabs = QTabWidget()
        for plugin in registry.available_plugins():
            browser = plugin.browser_class(db)
            if browser.has_settings():
                settings_widget = browser.create_settings_widget(parent=self)
                if settings_widget is not None:
                    connector_tabs.addTab(settings_widget, plugin.display_name)
        if connector_tabs.count() > 0:
            self._tabs.addTab(connector_tabs, "Connectors")

        self._audio_tab = AudioTab(audio_mgr, db=db)
        self._tabs.addTab(self._audio_tab, "Audio")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        self.settings_changed.emit()
        self.accept()
