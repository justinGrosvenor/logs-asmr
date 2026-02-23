"""Tests for LokiTailWorker — JSON frame parsing."""

from __future__ import annotations

import json

import pytest

websockets = pytest.importorskip("websockets")

from logs_asmr.connectors.loki.worker import LokiTailWorker
from logs_asmr.models.log_event import Level
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer


@pytest.fixture()
def ring():
    return RingBuffer(capacity=256)


class TestLokiProcessFrame:
    """Test _process_frame directly — no async/websocket needed."""

    def _make_worker(self, ring: RingBuffer) -> LokiTailWorker:
        source = Source(
            connector="loki",
            params={"url": "http://localhost:3100", "query": '{job="app"}'},
        )
        return LokiTailWorker(ring, source)

    def test_single_stream_single_value(self, ring: RingBuffer):
        worker = self._make_worker(ring)
        frame = {
            "streams": [
                {
                    "stream": {"job": "myapp"},
                    "values": [
                        ["1700000000000000000", "INFO Starting up"],
                    ],
                }
            ]
        }
        worker._process_frame(frame)

        events = ring.drain()
        assert len(events) == 1
        assert events[0].message == "INFO Starting up"
        assert events[0].log_group == "myapp"
        # 1700000000000000000 ns → 1700000000000 ms
        assert events[0].timestamp == 1700000000000

    def test_multiple_streams(self, ring: RingBuffer):
        worker = self._make_worker(ring)
        frame = {
            "streams": [
                {
                    "stream": {"job": "web"},
                    "values": [
                        ["1700000000000000000", "request served"],
                    ],
                },
                {
                    "stream": {"job": "api"},
                    "values": [
                        ["1700000001000000000", "query executed"],
                    ],
                },
            ]
        }
        worker._process_frame(frame)

        events = ring.drain()
        assert len(events) == 2
        assert events[0].log_group == "web"
        assert events[1].log_group == "api"

    def test_multiple_values_per_stream(self, ring: RingBuffer):
        worker = self._make_worker(ring)
        frame = {
            "streams": [
                {
                    "stream": {"job": "app"},
                    "values": [
                        ["1700000000000000000", "line one"],
                        ["1700000001000000000", "line two"],
                        ["1700000002000000000", "line three"],
                    ],
                }
            ]
        }
        worker._process_frame(frame)

        events = ring.drain()
        assert len(events) == 3
        assert [e.message for e in events] == ["line one", "line two", "line three"]

    def test_level_detection(self, ring: RingBuffer):
        worker = self._make_worker(ring)
        frame = {
            "streams": [
                {
                    "stream": {"job": "app"},
                    "values": [
                        ["1700000000000000000", "ERROR disk full"],
                        ["1700000001000000000", "DEBUG checking cache"],
                    ],
                }
            ]
        }
        worker._process_frame(frame)

        events = ring.drain()
        assert events[0].level == Level.ERROR
        assert events[1].level == Level.DEBUG

    def test_app_label_fallback(self, ring: RingBuffer):
        worker = self._make_worker(ring)
        frame = {
            "streams": [
                {
                    "stream": {"app": "frontend"},
                    "values": [["1700000000000000000", "hello"]],
                }
            ]
        }
        worker._process_frame(frame)

        events = ring.drain()
        assert events[0].log_group == "frontend"

    def test_empty_streams(self, ring: RingBuffer):
        worker = self._make_worker(ring)
        worker._process_frame({"streams": []})
        assert ring.drain() == []

    def test_ws_url_construction(self, ring: RingBuffer):
        source = Source(
            connector="loki",
            params={"url": "http://loki:3100", "query": '{job="x"}'},
        )
        worker = LokiTailWorker(ring, source)
        assert worker._url == "http://loki:3100"
        assert worker._query == '{job="x"}'

    def test_org_id_stored(self, ring: RingBuffer):
        source = Source(
            connector="loki",
            params={"url": "http://loki:3100", "org_id": "tenant-1"},
        )
        worker = LokiTailWorker(ring, source)
        assert worker._org_id == "tenant-1"
