"""Log viewport widget based on QPlainTextEdit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QPlainTextEdit

from logs_asmr.constants import MAX_LOG_LINES
from logs_asmr.ui import theme
from logs_asmr.ui.log_highlighter import LogHighlighter

if TYPE_CHECKING:
    from logs_asmr.models.log_event import LogEvent

logger = logging.getLogger("logs_asmr.log_view")


class LogView(QPlainTextEdit):
    """Virtualized, append-only log viewport."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self._auto_scroll = True

    def _setup_ui(self) -> None:
        self.setReadOnly(True)
        self.setMaximumBlockCount(MAX_LOG_LINES)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setUndoRedoEnabled(False)

        font = QFont("Menlo, Consolas, Monaco, monospace")
        font.setPointSize(12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        self.setStyleSheet(theme.log_view_style())

        self._highlighter = LogHighlighter(self.document())

    def append_events(self, events: list[LogEvent]) -> None:
        """Append a batch of log events efficiently."""
        if not events:
            return

        self.setUpdatesEnabled(False)
        try:
            for event in events:
                self.appendPlainText(event.display_line)
        finally:
            self.setUpdatesEnabled(True)

        if self._auto_scroll:
            self._scroll_to_bottom()

    def replace_all(self, events: list[LogEvent]) -> None:
        """Replace all content with the given events (used after re-filtering)."""
        self.setUpdatesEnabled(False)
        try:
            self.clear()
            for event in events:
                self.appendPlainText(event.display_line)
        finally:
            self.setUpdatesEnabled(True)

        if self._auto_scroll:
            self._scroll_to_bottom()

    def set_auto_scroll(self, enabled: bool) -> None:
        self._auto_scroll = enabled
        if enabled:
            self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())
