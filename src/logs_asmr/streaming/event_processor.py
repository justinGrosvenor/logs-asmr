"""Timer-driven event processor: drains ring buffer, applies filters, emits batches."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from logs_asmr.constants import MAX_COMPONENT_CHIPS, PROCESS_INTERVAL_MS
from logs_asmr.models.log_event import Level
from logs_asmr.streaming.filter_engine import FilterEngine

if TYPE_CHECKING:
    from logs_asmr.models.filter_state import FilterState
    from logs_asmr.models.log_event import LogEvent
    from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.event_processor")


class EventProcessor(QObject):
    """Drains the ring buffer on a timer, filters events, and emits display batches."""

    filtered_batch = pyqtSignal(list)  # list[LogEvent] — incremental append
    refiltered_all = pyqtSignal(list)  # list[LogEvent] — full replace after filter change
    error_batch = pyqtSignal(int)  # count of errors in this batch
    drop_count_updated = pyqtSignal(int)
    components_discovered = pyqtSignal(list)  # list[str]
    event_rate_updated = pyqtSignal(float)

    def __init__(self, ring_buffer: RingBuffer, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._buffer = ring_buffer
        self._filter = FilterEngine()
        self._timer = QTimer(self)
        self._timer.setInterval(PROCESS_INTERVAL_MS)
        self._timer.timeout.connect(self._process)
        self._paused = False

        # All events held for re-filtering
        self._all_events: list[LogEvent] = []
        self._max_events = ring_buffer._capacity

        # Component tracking
        self._known_components: set[str] = set()

        # Rate tracking
        self._rate_count = 0
        self._rate_time = time.monotonic()
        self._last_drop_count = 0

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def update_filter(self, state: FilterState) -> None:
        """Update filter and re-filter all held events."""
        self._filter.update(state)
        filtered = self._filter.filter_batch(self._all_events)
        self.refiltered_all.emit(filtered)

    def clear(self) -> None:
        """Clear all held events."""
        self._all_events.clear()
        self._known_components.clear()

    def _process(self) -> None:
        """Drain buffer and emit filtered batch."""
        events = self._buffer.drain()
        if not events and self._buffer.drop_count == self._last_drop_count:
            return

        # Track drops
        current_drops = self._buffer.drop_count
        if current_drops != self._last_drop_count:
            self._last_drop_count = current_drops
            self.drop_count_updated.emit(current_drops)

        if not events:
            return

        # Accumulate for re-filtering
        self._all_events.extend(events)
        if len(self._all_events) > self._max_events:
            self._all_events = self._all_events[-self._max_events :]

        # Update rate
        self._rate_count += len(events)
        now = time.monotonic()
        elapsed = now - self._rate_time
        if elapsed >= 1.0:
            rate = self._rate_count / elapsed
            self.event_rate_updated.emit(rate)
            self._rate_count = 0
            self._rate_time = now

        # Discover components
        new_components: list[str] = []
        for event in events:
            if (
                event.component
                and event.component not in self._known_components
                and len(self._known_components) < MAX_COMPONENT_CHIPS
            ):
                self._known_components.add(event.component)
                new_components.append(event.component)
        if new_components:
            self.components_discovered.emit(new_components)

        # Audio: count errors in unfiltered batch (error rate should reflect all events)
        error_count = sum(1 for e in events if e.level >= Level.ERROR)
        self.error_batch.emit(error_count)

        if self._paused:
            return

        # Filter
        filtered = self._filter.filter_batch(events)
        if filtered:
            self.filtered_batch.emit(filtered)
