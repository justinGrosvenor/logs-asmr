"""Tests for the event processor."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


from PyQt6.QtWidgets import QApplication

from logs_asmr.models.filter_state import FilterState
from logs_asmr.models.log_event import Level, LogEvent
from logs_asmr.streaming.event_processor import EventProcessor
from logs_asmr.streaming.ring_buffer import RingBuffer

# Ensure QApplication exists for signal/slot
_app = QApplication.instance() or QApplication([])


def _event(msg: str = "test", level: Level = Level.INFO, component: str = "") -> LogEvent:
    return LogEvent(timestamp=1000, message=msg, level=level, component=component)


def test_process_drains_buffer():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    batches = []
    proc.filtered_batch.connect(lambda b: batches.append(b))

    buf.push(_event("hello"))
    buf.push(_event("world"))
    proc._process()

    assert len(batches) == 1
    assert len(batches[0]) == 2


def test_process_applies_filter():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    batches = []
    proc.filtered_batch.connect(lambda b: batches.append(b))

    proc.update_filter(FilterState(levels={Level.ERROR}))

    buf.push(_event("err", Level.ERROR))
    buf.push(_event("info", Level.INFO))
    proc._process()

    assert len(batches) == 1
    assert len(batches[0]) == 1
    assert batches[0][0].message == "err"


def test_process_emits_error_batch_with_count():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    counts = []
    proc.error_batch.connect(lambda c: counts.append(c))

    buf.push(_event("ERROR: boom", Level.ERROR))
    buf.push(_event("all good", Level.INFO))
    buf.push(_event("ERROR: crash", Level.ERROR))
    proc._process()

    assert len(counts) == 1
    assert counts[0] == 2


def test_process_emits_zero_error_batch():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    counts = []
    proc.error_batch.connect(lambda c: counts.append(c))

    buf.push(_event("all good", Level.INFO))
    proc._process()

    assert len(counts) == 1
    assert counts[0] == 0


def test_process_discovers_components():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    discovered = []
    proc.components_discovered.connect(lambda c: discovered.extend(c))

    buf.push(_event("test", component="auth"))
    buf.push(_event("test", component="payments"))
    proc._process()

    assert set(discovered) == {"auth", "payments"}


def test_process_does_not_duplicate_components():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    discovered = []
    proc.components_discovered.connect(lambda c: discovered.extend(c))

    buf.push(_event("test", component="auth"))
    proc._process()
    buf.push(_event("test", component="auth"))
    proc._process()

    assert discovered == ["auth"]


def test_paused_skips_emit():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    batches = []
    proc.filtered_batch.connect(lambda b: batches.append(b))

    proc.set_paused(True)
    buf.push(_event("hello"))
    proc._process()

    assert len(batches) == 0


def test_paused_still_accumulates():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    proc.set_paused(True)
    buf.push(_event("hello"))
    proc._process()

    assert len(proc._all_events) == 1


def test_update_filter_emits_refiltered_all():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    refiltered = []
    proc.refiltered_all.connect(lambda b: refiltered.append(b))

    # Push and process some events
    buf.push(_event("ERROR: bad", Level.ERROR))
    buf.push(_event("all good", Level.INFO))
    proc._process()

    # Now change filter — should re-filter held events
    proc.update_filter(FilterState(levels={Level.ERROR}))
    assert len(refiltered) == 1
    assert len(refiltered[0]) == 1
    assert refiltered[0][0].message == "ERROR: bad"


def test_clear_resets_state():
    buf = RingBuffer(capacity=100)
    proc = EventProcessor(buf)

    buf.push(_event("test", component="auth"))
    proc._process()

    proc.clear()
    assert len(proc._all_events) == 0
    assert len(proc._known_components) == 0


def test_drop_count_updated():
    buf = RingBuffer(capacity=2)
    proc = EventProcessor(buf)

    drops = []
    proc.drop_count_updated.connect(lambda d: drops.append(d))

    for i in range(5):
        buf.push(_event(f"msg{i}"))
    proc._process()

    assert len(drops) == 1
    assert drops[0] == 3


def test_all_events_capped_at_capacity():
    buf = RingBuffer(capacity=5)
    proc = EventProcessor(buf)

    for i in range(10):
        buf.push(_event(f"msg{i}"))
    proc._process()

    # _all_events should not exceed buffer capacity
    assert len(proc._all_events) <= 5
