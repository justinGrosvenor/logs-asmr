"""Tests for DockerTailWorker with mocked docker SDK."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

docker = pytest.importorskip("docker")

from logs_asmr.connectors.docker.worker import DockerTailWorker
from logs_asmr.models.log_event import Level
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer


@pytest.fixture()
def ring():
    return RingBuffer(capacity=256)


class TestDockerTailWorker:
    def test_streams_container_logs(self, ring: RingBuffer):
        source = Source(
            connector="docker",
            params={"container_id": "abc123", "container_name": "web-1"},
        )
        worker = DockerTailWorker(ring, source)

        mock_container = MagicMock()
        mock_container.logs.return_value = iter([
            b"INFO Starting server\n",
            b"ERROR Connection refused\n",
        ])

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        with patch("docker.from_env", return_value=mock_client):
            worker.run()

        events = ring.drain()
        assert len(events) == 2
        assert events[0].message == "INFO Starting server"
        assert events[0].log_group == "web-1"
        assert events[1].level == Level.ERROR
        assert "connected" in statuses
        assert "disconnected" in statuses

    def test_connection_error(self, ring: RingBuffer):
        source = Source(
            connector="docker",
            params={"container_id": "bad"},
        )
        worker = DockerTailWorker(ring, source)

        errors = []
        worker.signals.error_occurred.connect(errors.append)

        with patch("docker.from_env", side_effect=Exception("Docker not running")):
            worker.run()

        assert len(errors) == 1
        assert "Docker" in errors[0]

    def test_multiline_chunk(self, ring: RingBuffer):
        source = Source(
            connector="docker",
            params={"container_id": "abc123", "container_name": "api"},
        )
        worker = DockerTailWorker(ring, source)

        mock_container = MagicMock()
        mock_container.logs.return_value = iter([
            b"line one\nline two\nline three\n",
        ])

        mock_client = MagicMock()
        mock_client.containers.get.return_value = mock_container

        with patch("docker.from_env", return_value=mock_client):
            worker.run()

        events = ring.drain()
        assert len(events) == 3
        assert events[0].message == "line one"
        assert events[2].message == "line three"

    def test_uses_container_id_as_name_fallback(self, ring: RingBuffer):
        source = Source(
            connector="docker",
            params={"container_id": "deadbeef"},
        )
        worker = DockerTailWorker(ring, source)
        assert worker._container_name == "deadbeef"
