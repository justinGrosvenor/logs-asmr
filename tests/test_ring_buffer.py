"""Tests for the SPSC ring buffer."""

from __future__ import annotations

import threading

from logs_asmr.models.log_event import LogEvent
from logs_asmr.streaming.ring_buffer import RingBuffer


def _event(msg: str = "test") -> LogEvent:
    return LogEvent(timestamp=1000, message=msg)


def test_push_pop_basic():
    buf = RingBuffer(capacity=5)
    buf.push(_event("a"))
    buf.push(_event("b"))
    assert buf.count == 2
    events = buf.drain()
    assert len(events) == 2
    assert events[0].message == "a"
    assert events[1].message == "b"
    assert buf.count == 0


def test_buffer_full_drops_oldest():
    buf = RingBuffer(capacity=3)
    for i in range(5):
        buf.push(_event(f"msg{i}"))
    assert buf.drop_count == 2
    assert buf.count == 3
    events = buf.drain()
    assert [e.message for e in events] == ["msg2", "msg3", "msg4"]


def test_drain_empty():
    buf = RingBuffer(capacity=5)
    events = buf.drain()
    assert events == []


def test_drain_with_limit():
    buf = RingBuffer(capacity=10)
    for i in range(7):
        buf.push(_event(f"msg{i}"))
    events = buf.drain(max_items=3)
    assert len(events) == 3
    assert buf.count == 4


def test_push_batch():
    buf = RingBuffer(capacity=5)
    batch = [_event(f"b{i}") for i in range(3)]
    buf.push_batch(batch)
    assert buf.count == 3
    assert buf.total_pushed == 3


def test_push_batch_overflow():
    buf = RingBuffer(capacity=3)
    batch = [_event(f"b{i}") for i in range(5)]
    buf.push_batch(batch)
    assert buf.drop_count == 2
    events = buf.drain()
    assert [e.message for e in events] == ["b2", "b3", "b4"]


def test_clear():
    buf = RingBuffer(capacity=5)
    for i in range(5):
        buf.push(_event(f"msg{i}"))
    buf.clear()
    assert buf.count == 0
    assert buf.drop_count == 0
    assert buf.total_pushed == 0


def test_reset_drop_count():
    buf = RingBuffer(capacity=2)
    for i in range(5):
        buf.push(_event(f"msg{i}"))
    assert buf.drop_count == 3
    buf.reset_drop_count()
    assert buf.drop_count == 0


def test_concurrent_push_drain():
    buf = RingBuffer(capacity=1000)
    produced = []
    consumed = []

    def producer():
        for i in range(500):
            buf.push(_event(f"p{i}"))
            produced.append(i)

    def consumer():
        while len(consumed) < 500:
            events = buf.drain()
            consumed.extend(e.message for e in events)

    t1 = threading.Thread(target=producer)
    t2 = threading.Thread(target=consumer)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    assert len(consumed) == 500
    assert buf.drop_count == 0
