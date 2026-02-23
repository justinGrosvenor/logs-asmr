"""Tests for JournaldTailWorker — mocked subprocess JSON line parsing."""

from __future__ import annotations

import json
import time
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from logs_asmr.connectors.journald.worker import JournaldTailWorker, _PRIORITY_MAP
from logs_asmr.models.log_event import Level
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer


@pytest.fixture()
def ring():
    return RingBuffer(capacity=256)


def _journal_entry(
    message: str = "test message",
    unit: str = "nginx.service",
    identifier: str = "nginx",
    priority: int = 6,
    ts_us: int | None = None,
) -> str:
    entry = {
        "MESSAGE": message,
        "_SYSTEMD_UNIT": unit,
        "SYSLOG_IDENTIFIER": identifier,
        "PRIORITY": str(priority),
        "__REALTIME_TIMESTAMP": str(ts_us or int(time.time() * 1_000_000)),
    }
    return json.dumps(entry)


class TestJournaldTailWorker:
    def test_parses_json_entries(self, ring: RingBuffer):
        source = Source(
            connector="journald",
            params={"unit": "nginx.service", "boot": "0"},
        )
        worker = JournaldTailWorker(ring, source)

        lines = "\n".join([
            _journal_entry(message="Starting nginx", priority=6),
            _journal_entry(message="Segfault in module", priority=3),
        ]) + "\n"

        mock_proc = MagicMock()
        mock_proc.stdout = StringIO(lines)
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        with patch("logs_asmr.connectors.journald.worker.subprocess") as mock_sub:
            mock_sub.Popen.return_value = mock_proc
            worker.run()

        events = ring.drain()
        assert len(events) == 2
        assert events[0].message == "Starting nginx"
        assert events[0].level == Level.INFO
        assert events[1].message == "Segfault in module"
        assert events[1].level == Level.ERROR
        assert "connected" in statuses
        assert "disconnected" in statuses

    def test_timestamp_conversion(self, ring: RingBuffer):
        source = Source(connector="journald", params={"boot": "0"})
        worker = JournaldTailWorker(ring, source)

        ts_us = 1700000000_123456  # microseconds
        lines = _journal_entry(ts_us=ts_us) + "\n"

        mock_proc = MagicMock()
        mock_proc.stdout = StringIO(lines)
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        with patch("logs_asmr.connectors.journald.worker.subprocess") as mock_sub:
            mock_sub.Popen.return_value = mock_proc
            worker.run()

        events = ring.drain()
        assert events[0].timestamp == ts_us // 1000

    def test_binary_message_decoded(self, ring: RingBuffer):
        source = Source(connector="journald", params={"boot": "0"})
        worker = JournaldTailWorker(ring, source)

        # journald encodes binary messages as byte arrays
        entry = {
            "MESSAGE": [72, 101, 108, 108, 111],  # "Hello"
            "__REALTIME_TIMESTAMP": str(int(time.time() * 1_000_000)),
            "PRIORITY": "6",
        }
        lines = json.dumps(entry) + "\n"

        mock_proc = MagicMock()
        mock_proc.stdout = StringIO(lines)
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        with patch("logs_asmr.connectors.journald.worker.subprocess") as mock_sub:
            mock_sub.Popen.return_value = mock_proc
            worker.run()

        events = ring.drain()
        assert events[0].message == "Hello"

    def test_priority_mapping(self):
        assert _PRIORITY_MAP[0] == Level.ERROR  # emerg
        assert _PRIORITY_MAP[3] == Level.ERROR  # err
        assert _PRIORITY_MAP[4] == Level.WARN   # warning
        assert _PRIORITY_MAP[5] == Level.INFO   # notice
        assert _PRIORITY_MAP[6] == Level.INFO   # info
        assert _PRIORITY_MAP[7] == Level.DEBUG  # debug

    def test_log_group_from_unit(self, ring: RingBuffer):
        source = Source(connector="journald", params={"boot": "0"})
        worker = JournaldTailWorker(ring, source)

        lines = _journal_entry(unit="sshd.service", identifier="sshd") + "\n"

        mock_proc = MagicMock()
        mock_proc.stdout = StringIO(lines)
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        with patch("logs_asmr.connectors.journald.worker.subprocess") as mock_sub:
            mock_sub.Popen.return_value = mock_proc
            worker.run()

        events = ring.drain()
        assert events[0].log_group == "sshd.service"
        assert events[0].log_stream == "sshd"
        assert events[0].component == "sshd"

    def test_journalctl_not_found(self, ring: RingBuffer):
        source = Source(connector="journald", params={"boot": "0"})
        worker = JournaldTailWorker(ring, source)

        errors = []
        worker.signals.error_occurred.connect(errors.append)

        with patch("logs_asmr.connectors.journald.worker.subprocess") as mock_sub:
            mock_sub.Popen.side_effect = FileNotFoundError("journalctl")
            worker.run()

        assert len(errors) == 1
        assert "journalctl" in errors[0].lower()

    def test_non_json_line_emitted_as_is(self, ring: RingBuffer):
        source = Source(connector="journald", params={"boot": "0"})
        worker = JournaldTailWorker(ring, source)

        lines = "-- Logs begin at Mon 2025-01-01 --\n"

        mock_proc = MagicMock()
        mock_proc.stdout = StringIO(lines)
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        with patch("logs_asmr.connectors.journald.worker.subprocess") as mock_sub:
            mock_sub.Popen.return_value = mock_proc
            worker.run()

        events = ring.drain()
        assert len(events) == 1
        assert "Logs begin" in events[0].message

    def test_cmd_includes_unit_flag(self, ring: RingBuffer):
        source = Source(
            connector="journald",
            params={"unit": "nginx.service", "boot": "0"},
        )
        worker = JournaldTailWorker(ring, source)

        mock_proc = MagicMock()
        mock_proc.stdout = StringIO("")
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()

        with patch("logs_asmr.connectors.journald.worker.subprocess") as mock_sub:
            mock_sub.Popen.return_value = mock_proc
            worker.run()

            cmd = mock_sub.Popen.call_args[0][0]
            assert "--unit=nginx.service" in cmd
            assert "--boot=0" in cmd
