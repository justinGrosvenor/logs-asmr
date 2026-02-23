"""Tests for KubernetesTailWorker with mocked kubernetes SDK."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

kubernetes = pytest.importorskip("kubernetes")

from logs_asmr.connectors.kubernetes.worker import KubernetesTailWorker
from logs_asmr.models.log_event import Level
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer


@pytest.fixture()
def ring():
    return RingBuffer(capacity=256)


class TestKubernetesTailWorker:
    def test_streams_pod_logs(self, ring: RingBuffer):
        source = Source(
            connector="kubernetes",
            params={
                "context": "minikube",
                "namespace": "default",
                "pod": "web-abc123",
                "container": "app",
            },
        )
        worker = KubernetesTailWorker(ring, source)

        statuses = []
        worker.signals.status_changed.connect(statuses.append)

        mock_watch = MagicMock()
        mock_watch.stream.return_value = iter([
            "INFO Request received\n",
            "WARN Slow query\n",
        ])

        with (
            patch("kubernetes.config.new_client_from_config"),
            patch("kubernetes.client.CoreV1Api"),
            patch("kubernetes.watch.Watch", return_value=mock_watch),
        ):
            worker.run()

        events = ring.drain()
        assert len(events) == 2
        assert events[0].message == "INFO Request received"
        assert events[0].log_group == "default/web-abc123"
        assert events[0].log_stream == "app"
        assert events[1].level == Level.WARN
        assert "connected" in statuses

    def test_connection_error(self, ring: RingBuffer):
        source = Source(
            connector="kubernetes",
            params={"namespace": "default", "pod": "web-abc123"},
        )
        worker = KubernetesTailWorker(ring, source)

        errors = []
        worker.signals.error_occurred.connect(errors.append)

        with patch(
            "kubernetes.config.new_client_from_config",
            side_effect=Exception("No kubeconfig"),
        ):
            worker.run()

        assert len(errors) == 1
        assert "Kubernetes" in errors[0]

    def test_bytes_decoded(self, ring: RingBuffer):
        source = Source(
            connector="kubernetes",
            params={"namespace": "default", "pod": "api-xyz", "container": "main"},
        )
        worker = KubernetesTailWorker(ring, source)

        mock_watch = MagicMock()
        mock_watch.stream.return_value = iter([
            b"binary log line\n",
        ])

        with (
            patch("kubernetes.config.new_client_from_config"),
            patch("kubernetes.client.CoreV1Api"),
            patch("kubernetes.watch.Watch", return_value=mock_watch),
        ):
            worker.run()

        events = ring.drain()
        assert len(events) == 1
        assert events[0].message == "binary log line"

    def test_default_namespace(self, ring: RingBuffer):
        source = Source(
            connector="kubernetes",
            params={"pod": "web"},
        )
        worker = KubernetesTailWorker(ring, source)
        assert worker._namespace == "default"
