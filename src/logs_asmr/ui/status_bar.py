"""Bottom status bar — connection state, drop count, event rate."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QStatusBar

from logs_asmr.ui import theme


class StatusBarManager:
    """Manages the status bar widgets."""

    def __init__(self, status_bar: QStatusBar) -> None:
        self._bar = status_bar

        self._status_label = QLabel("Ready")
        self._drop_label = QLabel("")
        self._rate_label = QLabel("")

        self._bar.addWidget(self._status_label, 1)
        self._bar.addPermanentWidget(self._rate_label)
        self._bar.addPermanentWidget(self._drop_label)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def set_drop_count(self, count: int) -> None:
        if count > 0:
            self._drop_label.setText(f"Dropped: {count:,}")
            self._drop_label.setStyleSheet(theme.drop_count_style())
        else:
            self._drop_label.setText("")

    def set_event_rate(self, rate: float) -> None:
        if rate > 0:
            self._rate_label.setText(f"{rate:.0f} events/s")
        else:
            self._rate_label.setText("")
