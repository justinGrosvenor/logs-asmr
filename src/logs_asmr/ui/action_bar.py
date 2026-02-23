"""Top action strip — compact toolbar matching native system window feel."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from logs_asmr.ui import theme
from logs_asmr.ui.theme import BADGE_COLORS, BADGE_DEFAULT_COLORS, Size


class ActionBar(QWidget):
    """Compact top action strip with controls and status indicators."""

    tail_toggled = pyqtSignal(bool)  # True = live, False = paused
    clear_clicked = pyqtSignal()
    catch_up_clicked = pyqtSignal()
    filter_drawer_toggled = pyqtSignal(bool)
    mute_toggled = pyqtSignal(bool)
    settings_clicked = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._is_live = True
        self._is_muted = False
        self._filter_open = False
        self.setFixedHeight(Size.BAR_HEIGHT)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(4)

        self.setStyleSheet(theme.action_bar_style())

        # Tail/Pause
        self._tail_btn = QPushButton("Pause")
        self._tail_btn.setFixedHeight(Size.BAR_HEIGHT - 6)
        self._tail_btn.setToolTip("Pause / Resume live tail (Space)")
        self._update_tail_btn_style()
        layout.addWidget(self._tail_btn)

        # Clear
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedHeight(Size.BAR_HEIGHT - 6)
        self._clear_btn.setToolTip("Clear log view (Ctrl+L)")
        layout.addWidget(self._clear_btn)

        # Catch-up (visible only when dropping)
        self._catchup_btn = QPushButton("Catch Up")
        self._catchup_btn.setFixedHeight(Size.BAR_HEIGHT - 6)
        self._catchup_btn.setVisible(False)
        self._catchup_btn.setToolTip("Clear buffer and resume live")
        self._catchup_btn.setStyleSheet(theme.catchup_btn_style())
        layout.addWidget(self._catchup_btn)

        # Filters toggle
        self._filter_btn = QPushButton("Filters")
        self._filter_btn.setFixedHeight(Size.BAR_HEIGHT - 6)
        self._filter_btn.setCheckable(True)
        self._filter_btn.setToolTip("Toggle filter drawer (Ctrl+F)")
        layout.addWidget(self._filter_btn)

        layout.addStretch()

        # Status badge — small, subtle pill
        self._status_badge = QLabel("Live")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_badge.setFixedHeight(Size.BAR_HEIGHT - 8)
        bg, fg = BADGE_COLORS["connected"]
        self._update_badge_style(bg, fg)
        layout.addWidget(self._status_badge)

        # Mute/Unmute
        self._mute_btn = QPushButton("Mute")
        self._mute_btn.setFixedHeight(Size.BAR_HEIGHT - 6)
        self._mute_btn.setToolTip("Toggle audio (M)")
        layout.addWidget(self._mute_btn)

        # Settings
        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setFixedHeight(Size.BAR_HEIGHT - 6)
        self._settings_btn.setToolTip("Open settings")
        layout.addWidget(self._settings_btn)

    def _connect_signals(self) -> None:
        self._tail_btn.clicked.connect(self._on_tail_clicked)
        self._clear_btn.clicked.connect(self.clear_clicked.emit)
        self._catchup_btn.clicked.connect(self.catch_up_clicked.emit)
        self._filter_btn.toggled.connect(self._on_filter_toggled)
        self._mute_btn.clicked.connect(self._on_mute_clicked)
        self._settings_btn.clicked.connect(self.settings_clicked.emit)

    def _on_tail_clicked(self) -> None:
        self._is_live = not self._is_live
        self._tail_btn.setText("Pause" if self._is_live else "Resume")
        self._update_tail_btn_style()
        self.tail_toggled.emit(self._is_live)
        self._update_status_badge()

    def _update_tail_btn_style(self) -> None:
        if self._is_live:
            self._tail_btn.setStyleSheet(theme.tail_btn_live_style())
        else:
            self._tail_btn.setStyleSheet(theme.tail_btn_paused_style())

    def _on_filter_toggled(self, checked: bool) -> None:
        self._filter_open = checked
        self.filter_drawer_toggled.emit(checked)

    def _on_mute_clicked(self) -> None:
        self._is_muted = not self._is_muted
        self._mute_btn.setText("Unmute" if self._is_muted else "Mute")
        self.mute_toggled.emit(self._is_muted)

    def _update_badge_style(self, bg: str, fg: str) -> None:
        self._status_badge.setStyleSheet(theme.badge_style(bg, fg))

    def set_status(self, status: str) -> None:
        """Update the status badge text and color."""
        bg, fg = BADGE_COLORS.get(status, BADGE_DEFAULT_COLORS)
        label = {
            "connected": "Live",
            "paused": "Paused",
            "dropping": "Dropping",
            "sampling": "Sampling",
            "reconnecting": "Reconnecting",
            "disconnected": "Disconnected",
        }.get(status, status.title())

        self._status_badge.setText(label)
        self._update_badge_style(bg, fg)

        # Show catch-up button only when dropping
        self._catchup_btn.setVisible(status == "dropping")

    def _update_status_badge(self) -> None:
        if self._is_live:
            self.set_status("connected")
        else:
            self.set_status("paused")

    @property
    def is_live(self) -> bool:
        return self._is_live

    @property
    def is_muted(self) -> bool:
        return self._is_muted

    def set_filter_checked(self, checked: bool) -> None:
        """Programmatically set the filter button state."""
        self._filter_btn.blockSignals(True)
        self._filter_btn.setChecked(checked)
        self._filter_btn.blockSignals(False)
        self._filter_open = checked
