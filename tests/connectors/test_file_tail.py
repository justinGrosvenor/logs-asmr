"""Tests for the file tail connector — real file I/O with tmp_path."""

from __future__ import annotations

import os
import time

import pytest

from logs_asmr.connectors.file_tail.worker import FileTailWorker
from logs_asmr.models.log_event import Level
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer


@pytest.fixture()
def ring():
    return RingBuffer(capacity=256)


class TestFileTailWorker:
    def test_file_not_found(self, ring: RingBuffer, qtbot):
        source = Source(connector="file", params={"path": "/nonexistent/file.log"})
        worker = FileTailWorker(ring, source)

        errors = []
        worker.signals.error_occurred.connect(errors.append)

        worker.run()

        assert len(errors) == 1
        assert "not found" in errors[0].lower()

    def test_tail_new_lines(self, ring: RingBuffer, tmp_path, qtbot):
        log_file = tmp_path / "app.log"
        log_file.write_text("")  # Create empty file

        source = Source(connector="file", params={"path": str(log_file)})
        worker = FileTailWorker(ring, source)

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        # Start worker in background
        worker.start()
        qtbot.waitUntil(lambda: "connected" in statuses, timeout=2000)

        # Write lines to the file
        with open(log_file, "a") as f:
            f.write("INFO first log line\n")
            f.write("ERROR something failed\n")
            f.flush()

        # Give the poll loop time to pick up the lines
        qtbot.waitUntil(lambda: ring._count >= 2, timeout=3000)

        worker.stop()
        worker.wait(2000)

        events = ring.drain()
        assert len(events) == 2
        assert events[0].message == "INFO first log line"
        assert events[1].message == "ERROR something failed"
        assert events[1].level == Level.ERROR

    def test_detects_file_rotation(self, ring: RingBuffer, tmp_path, qtbot):
        log_file = tmp_path / "rotated.log"
        log_file.write_text("")

        source = Source(connector="file", params={"path": str(log_file)})
        worker = FileTailWorker(ring, source)

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        worker.start()
        qtbot.waitUntil(lambda: "connected" in statuses, timeout=2000)

        # Write a line
        with open(log_file, "a") as f:
            f.write("before rotation\n")
            f.flush()

        qtbot.waitUntil(lambda: ring._count >= 1, timeout=3000)

        # Simulate rotation: remove and recreate
        log_file.unlink()
        log_file.write_text("after rotation\n")

        qtbot.waitUntil(lambda: ring._count >= 2, timeout=3000)

        worker.stop()
        worker.wait(2000)

        events = ring.drain()
        messages = [e.message for e in events]
        assert "before rotation" in messages
        assert "after rotation" in messages

    def test_log_group_is_path(self, ring: RingBuffer, tmp_path, qtbot):
        log_file = tmp_path / "group.log"
        log_file.write_text("")

        source = Source(connector="file", params={"path": str(log_file)})
        worker = FileTailWorker(ring, source)

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        worker.start()
        qtbot.waitUntil(lambda: "connected" in statuses, timeout=2000)

        with open(log_file, "a") as f:
            f.write("hello\n")
            f.flush()

        qtbot.waitUntil(lambda: ring._count >= 1, timeout=3000)

        worker.stop()
        worker.wait(2000)

        events = ring.drain()
        assert events[0].log_group == str(log_file)

    def test_empty_lines_skipped(self, ring: RingBuffer, tmp_path, qtbot):
        log_file = tmp_path / "blanks.log"
        log_file.write_text("")

        source = Source(connector="file", params={"path": str(log_file)})
        worker = FileTailWorker(ring, source)

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        worker.start()
        qtbot.waitUntil(lambda: "connected" in statuses, timeout=2000)

        with open(log_file, "a") as f:
            f.write("\n\n\nactual line\n\n")
            f.flush()

        qtbot.waitUntil(lambda: ring._count >= 1, timeout=3000)

        worker.stop()
        worker.wait(2000)

        events = ring.drain()
        assert len(events) == 1
        assert events[0].message == "actual line"
