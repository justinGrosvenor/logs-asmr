"""Thread-safe SPSC ring buffer for passing log events between threads."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from logs_asmr.constants import RING_BUFFER_CAPACITY

if TYPE_CHECKING:
    from logs_asmr.models.log_event import LogEvent


class RingBuffer:
    """Single-producer single-consumer ring buffer with drop counting.

    The network thread pushes events; the UI thread drains them in batches.
    When full, the oldest event is dropped and the drop counter increments.
    """

    def __init__(self, capacity: int = RING_BUFFER_CAPACITY) -> None:
        self._capacity = capacity
        self._buffer: list[LogEvent | None] = [None] * capacity
        self._head = 0  # next write position (producer)
        self._tail = 0  # next read position (consumer)
        self._count = 0
        self._lock = threading.Lock()
        self._drop_count = 0
        self._total_pushed = 0

    def push(self, event: LogEvent) -> None:
        """Push an event into the buffer. Drops oldest if full."""
        with self._lock:
            if self._count == self._capacity:
                # Drop oldest
                self._tail = (self._tail + 1) % self._capacity
                self._count -= 1
                self._drop_count += 1

            self._buffer[self._head] = event
            self._head = (self._head + 1) % self._capacity
            self._count += 1
            self._total_pushed += 1

    def push_batch(self, events: list[LogEvent]) -> None:
        """Push multiple events. More efficient than individual pushes."""
        with self._lock:
            for event in events:
                if self._count == self._capacity:
                    self._tail = (self._tail + 1) % self._capacity
                    self._count -= 1
                    self._drop_count += 1

                self._buffer[self._head] = event
                self._head = (self._head + 1) % self._capacity
                self._count += 1
                self._total_pushed += 1

    def drain(self, max_items: int = 0) -> list[LogEvent]:
        """Drain up to max_items events from the buffer. 0 means drain all."""
        with self._lock:
            if self._count == 0:
                return []

            n = self._count if max_items <= 0 else min(max_items, self._count)
            result: list[LogEvent] = []
            for _ in range(n):
                event = self._buffer[self._tail]
                self._buffer[self._tail] = None
                self._tail = (self._tail + 1) % self._capacity
                self._count -= 1
                if event is not None:
                    result.append(event)
            return result

    @property
    def drop_count(self) -> int:
        return self._drop_count

    @property
    def total_pushed(self) -> int:
        return self._total_pushed

    @property
    def count(self) -> int:
        return self._count

    def reset_drop_count(self) -> None:
        with self._lock:
            self._drop_count = 0

    def clear(self) -> None:
        """Clear all events and reset counters."""
        with self._lock:
            self._buffer = [None] * self._capacity
            self._head = 0
            self._tail = 0
            self._count = 0
            self._drop_count = 0
            self._total_pushed = 0
