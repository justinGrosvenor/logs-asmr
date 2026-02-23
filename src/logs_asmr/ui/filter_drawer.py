"""Non-modal filter drawer — Include/Exclude, Level chips, Component chips, Presets."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from logs_asmr.constants import FILTER_DEBOUNCE_MS
from logs_asmr.models.filter_state import FilterState
from logs_asmr.models.log_event import Level
from logs_asmr.ui import theme
from logs_asmr.ui.widgets.chip_bar import ChipBar

if TYPE_CHECKING:
    from logs_asmr.db.database import Database

logger = logging.getLogger("logs_asmr.filter_drawer")


class FilterDrawer(QDockWidget):
    """Non-modal filter drawer docked to the right side."""

    filter_changed = pyqtSignal(object)  # FilterState

    def __init__(self, parent=None, db: Database | None = None) -> None:
        super().__init__("Filters", parent)
        self._db = db
        self._log_group = ""
        self.setObjectName("FilterDrawer")
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(FILTER_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._emit_filter)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Presets
        preset_row = QHBoxLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("(no preset)")
        self._preset_combo.setMinimumWidth(120)
        preset_row.addWidget(self._preset_combo)
        self._save_preset_btn = QPushButton("Save")
        self._save_preset_btn.setFixedWidth(50)
        preset_row.addWidget(self._save_preset_btn)
        self._delete_preset_btn = QPushButton("Del")
        self._delete_preset_btn.setFixedWidth(40)
        preset_row.addWidget(self._delete_preset_btn)
        layout.addLayout(preset_row)

        # Include filter
        include_label = QLabel("Include")
        include_label.setStyleSheet(theme.section_heading_style())
        layout.addWidget(include_label)
        include_row = QHBoxLayout()
        self._include_input = QLineEdit()
        self._include_input.setPlaceholderText("Text or regex to include...")
        self._include_regex_cb = QCheckBox("Regex")
        include_row.addWidget(self._include_input)
        include_row.addWidget(self._include_regex_cb)
        layout.addLayout(include_row)

        # Exclude filter
        exclude_label = QLabel("Exclude")
        exclude_label.setStyleSheet(theme.section_heading_style())
        layout.addWidget(exclude_label)
        exclude_row = QHBoxLayout()
        self._exclude_input = QLineEdit()
        self._exclude_input.setPlaceholderText("Text or regex to exclude...")
        self._exclude_regex_cb = QCheckBox("Regex")
        exclude_row.addWidget(self._exclude_input)
        exclude_row.addWidget(self._exclude_regex_cb)
        layout.addLayout(exclude_row)

        # Level chips
        levels_label = QLabel("Levels")
        levels_label.setStyleSheet(theme.section_heading_style())
        layout.addWidget(levels_label)
        self._level_chips = ChipBar()
        self._level_chips.set_chips(["ERROR", "WARN", "INFO", "DEBUG"], all_selected=True)
        layout.addWidget(self._level_chips)

        # Component chips
        components_label = QLabel("Components")
        components_label.setStyleSheet(theme.section_heading_style())
        layout.addWidget(components_label)
        self._component_chips = ChipBar()
        layout.addWidget(self._component_chips)

        layout.addStretch()
        self.setWidget(container)
        self.setMinimumWidth(280)

    def _connect_signals(self) -> None:
        self._include_input.textChanged.connect(self._on_text_changed)
        self._exclude_input.textChanged.connect(self._on_text_changed)
        self._include_regex_cb.toggled.connect(self._on_text_changed)
        self._exclude_regex_cb.toggled.connect(self._on_text_changed)

        self._level_chips.selection_changed.connect(self._on_chips_changed)
        self._component_chips.selection_changed.connect(self._on_chips_changed)

        self._save_preset_btn.clicked.connect(self._on_save_preset)
        self._delete_preset_btn.clicked.connect(self._on_delete_preset)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)

    def _on_text_changed(self) -> None:
        self._debounce_timer.start()

    def _on_chips_changed(self, _selected: set) -> None:
        self._emit_filter()

    def _emit_filter(self) -> None:
        level_map = {
            "ERROR": Level.ERROR,
            "WARN": Level.WARN,
            "INFO": Level.INFO,
            "DEBUG": Level.DEBUG,
        }
        selected_levels = set()
        for name in self._level_chips.selected():
            if name in level_map:
                selected_levels.add(level_map[name])

        state = FilterState(
            include_text=self._include_input.text(),
            include_is_regex=self._include_regex_cb.isChecked(),
            exclude_text=self._exclude_input.text(),
            exclude_is_regex=self._exclude_regex_cb.isChecked(),
            levels=selected_levels if selected_levels else set(Level),
            components=self._component_chips.selected(),
        )
        self.filter_changed.emit(state)

    def add_components(self, names: list[str]) -> None:
        for name in names:
            self._component_chips.add_chip(name, selected=True)

    def set_db(self, db: Database) -> None:
        self._db = db
        self._load_presets()

    def set_log_group(self, log_group: str) -> None:
        self._log_group = log_group
        self._load_presets()

    # --- Presets ---

    def _load_presets(self) -> None:
        if self._db is None:
            return
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItem("(no preset)")

        rows = self._db.fetchall(
            "SELECT name FROM filter_presets WHERE log_group IN ('', ?) ORDER BY name",
            (self._log_group,),
        )
        for row in rows:
            self._preset_combo.addItem(row["name"], row["name"])

        self._preset_combo.blockSignals(False)

    def _on_save_preset(self) -> None:
        if self._db is None:
            return
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()

        level_names = ",".join(sorted(self._level_chips.selected()))
        self._db.execute(
            "INSERT OR REPLACE INTO filter_presets "
            "(name, log_group, include_text, include_is_regex, "
            "exclude_text, exclude_is_regex, levels) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                self._log_group,
                self._include_input.text(),
                1 if self._include_regex_cb.isChecked() else 0,
                self._exclude_input.text(),
                1 if self._exclude_regex_cb.isChecked() else 0,
                level_names,
            ),
        )
        self._load_presets()
        idx = self._preset_combo.findData(name)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        logger.info("Filter preset saved: %s", name)

    def _on_delete_preset(self) -> None:
        if self._db is None:
            return
        name = self._preset_combo.currentData()
        if not name:
            return
        self._db.execute(
            "DELETE FROM filter_presets WHERE name = ? AND log_group IN ('', ?)",
            (name, self._log_group),
        )
        self._load_presets()
        logger.info("Filter preset deleted: %s", name)

    def _on_preset_selected(self, index: int) -> None:
        if self._db is None or index <= 0:
            return
        name = self._preset_combo.currentData()
        if not name:
            return

        row = self._db.fetchone(
            "SELECT * FROM filter_presets WHERE name = ? AND log_group IN ('', ?) LIMIT 1",
            (name, self._log_group),
        )
        if not row:
            return

        self._include_input.blockSignals(True)
        self._exclude_input.blockSignals(True)
        self._include_regex_cb.blockSignals(True)
        self._exclude_regex_cb.blockSignals(True)

        self._include_input.setText(row["include_text"] or "")
        self._include_regex_cb.setChecked(bool(row["include_is_regex"]))
        self._exclude_input.setText(row["exclude_text"] or "")
        self._exclude_regex_cb.setChecked(bool(row["exclude_is_regex"]))

        self._include_input.blockSignals(False)
        self._exclude_input.blockSignals(False)
        self._include_regex_cb.blockSignals(False)
        self._exclude_regex_cb.blockSignals(False)

        self._emit_filter()
        logger.info("Filter preset loaded: %s", name)
