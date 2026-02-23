"""Compiled filter logic for log events."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logs_asmr.models.filter_state import FilterState
    from logs_asmr.models.log_event import LogEvent

logger = logging.getLogger("logs_asmr.filter_engine")

#: Regex metacharacters that indicate a pattern is not plain text.
_REGEX_META = re.compile(r"[\\.*+?^${}()|[\]]")


class FilterEngine:
    """Applies filters to log events with compiled regex and fast paths."""

    def __init__(self) -> None:
        self._include_pattern: re.Pattern | None = None
        self._include_plain: str = ""
        self._exclude_pattern: re.Pattern | None = None
        self._exclude_plain: str = ""
        self._filter_state: FilterState | None = None

    def update(self, state: FilterState) -> None:
        """Recompile patterns when filter state changes."""
        self._filter_state = state

        # Include
        if state.include_text:
            if state.include_is_regex:
                self._include_pattern = _safe_compile(state.include_text)
                self._include_plain = "" if self._include_pattern else state.include_text
            else:
                self._include_pattern = None
                self._include_plain = state.include_text.lower()
        else:
            self._include_pattern = None
            self._include_plain = ""

        # Exclude
        if state.exclude_text:
            if state.exclude_is_regex:
                self._exclude_pattern = _safe_compile(state.exclude_text)
                self._exclude_plain = "" if self._exclude_pattern else state.exclude_text
            else:
                self._exclude_pattern = None
                self._exclude_plain = state.exclude_text.lower()
        else:
            self._exclude_pattern = None
            self._exclude_plain = ""

    def matches(self, event: LogEvent) -> bool:
        """Return True if the event passes all active filters."""
        state = self._filter_state
        if state is None:
            return True

        # Level check (cheapest)
        if event.level not in state.levels:
            return False

        # Component filter
        if state.components and event.component and event.component not in state.components:
            return False

        # Exclude (reject fast)
        if self._exclude_pattern:
            if self._exclude_pattern.search(event.message):
                return False
        elif self._exclude_plain and self._exclude_plain in event.message.lower():
            return False

        # Include
        if self._include_pattern:
            if not self._include_pattern.search(event.message):
                return False
        elif self._include_plain and self._include_plain not in event.message.lower():
            return False

        return True

    def filter_batch(self, events: list[LogEvent]) -> list[LogEvent]:
        """Filter a batch of events. Returns only matching events."""
        if self._filter_state is None or self._filter_state.is_default:
            return events
        return [e for e in events if self.matches(e)]


def _safe_compile(pattern: str) -> re.Pattern | None:
    """Compile a regex pattern, returning None on invalid syntax."""
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        logger.debug("Invalid regex pattern, falling back to literal: %s", pattern)
        return None
