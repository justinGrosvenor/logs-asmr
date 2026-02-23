"""Syntax highlighter for log level coloring."""

from __future__ import annotations

import re

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat

from logs_asmr.ui.theme import HighlightColor


class LogHighlighter(QSyntaxHighlighter):
    """Highlights log lines by severity level based on the level column."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._error_fmt = QTextCharFormat()
        self._error_fmt.setForeground(HighlightColor.ERROR)

        self._warn_fmt = QTextCharFormat()
        self._warn_fmt.setForeground(HighlightColor.WARN)

        self._debug_fmt = QTextCharFormat()
        self._debug_fmt.setForeground(HighlightColor.DEBUG)

        self._info_fmt = QTextCharFormat()
        self._info_fmt.setForeground(HighlightColor.INFO)

        self._timestamp_fmt = QTextCharFormat()
        self._timestamp_fmt.setForeground(HighlightColor.TIMESTAMP)

        # Match the level field in "YYYY-MM-DD HH:MM:SS.mmm | LEVEL | message"
        self._level_pattern = re.compile(r"\|\s*(ERROR|WARN|INFO|DEBUG)\s*\|")

    def highlightBlock(self, text: str) -> None:
        if not text:
            return

        # Color the timestamp portion (first 23 chars)
        if len(text) > 23 and text[4] == "-":
            self.setFormat(0, 23, self._timestamp_fmt)

        # Detect level and color the entire line
        m = self._level_pattern.search(text)
        if not m:
            return

        level = m.group(1)
        if level == "ERROR":
            fmt = self._error_fmt
        elif level == "WARN":
            fmt = self._warn_fmt
        elif level == "DEBUG":
            fmt = self._debug_fmt
        else:
            fmt = self._info_fmt

        # Color from the level field onward
        self.setFormat(m.start(), len(text) - m.start(), fmt)
