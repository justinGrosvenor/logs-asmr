"""Tests for GCPTailWorker with mocked GCP client."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

gcp_logging = pytest.importorskip("google.cloud.logging")

from logs_asmr.connectors.gcp.worker import GCPTailWorker
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer


@pytest.fixture()
def ring():
    return RingBuffer(capacity=256)


def _make_entry(payload: str, timestamp: datetime | None = None, log_name: str = "syslog"):
    entry = MagicMock()
    entry.payload = payload
    entry.timestamp = timestamp or datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
    entry.log_name = log_name
    entry.resource = MagicMock()
    entry.resource.type = "gce_instance"
    return entry


class TestGCPTailWorker:
    def test_polls_and_pushes_entries(self, ring: RingBuffer):
        source = Source(
            connector="gcp",
            params={"project": "my-project", "log_name": "syslog"},
        )
        worker = GCPTailWorker(ring, source)

        entries = [
            _make_entry("INFO Starting up"),
            _make_entry("ERROR Disk full"),
        ]

        mock_client = MagicMock()
        call_count = 0

        def fake_list_entries(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return entries
            worker._running = False
            return []

        mock_client.list_entries = fake_list_entries

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        with patch("google.cloud.logging.Client", return_value=mock_client):
            worker.run()

        events = ring.drain()
        assert len(events) == 2
        assert events[0].message == "INFO Starting up"
        assert events[0].log_group == "gce_instance"
        assert events[0].log_stream == "syslog"
        assert "connected" in statuses

    def test_connection_error(self, ring: RingBuffer):
        source = Source(
            connector="gcp",
            params={"project": "bad-project"},
        )
        worker = GCPTailWorker(ring, source)

        errors = []
        worker.signals.error_occurred.connect(errors.append)

        with patch("google.cloud.logging.Client", side_effect=Exception("Auth failed")):
            worker.run()

        assert len(errors) == 1
        assert "GCP" in errors[0]

    def test_timestamp_conversion(self, ring: RingBuffer):
        source = Source(
            connector="gcp",
            params={"project": "test"},
        )
        worker = GCPTailWorker(ring, source)

        ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        entries = [_make_entry("test", timestamp=ts)]

        mock_client = MagicMock()
        call_count = 0

        def fake_list(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return entries
            worker._running = False
            return []

        mock_client.list_entries = fake_list

        with patch("google.cloud.logging.Client", return_value=mock_client):
            worker.run()

        events = ring.drain()
        assert events[0].timestamp == int(ts.timestamp() * 1000)
