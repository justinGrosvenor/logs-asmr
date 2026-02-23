"""LokiTailWorker — streams logs via Loki's WebSocket tail endpoint."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from logs_asmr.connectors.base import TailWorker
from logs_asmr.models.log_event import LogEvent, detect_level

if TYPE_CHECKING:
    from PyQt6.QtCore import QObject

    from logs_asmr.models.source import Source
    from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.connectors.loki.worker")


class LokiTailWorker(TailWorker):
    """Streams log entries from Grafana Loki via WebSocket tail API."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, source, parent)
        self._url = source.param("url", "http://localhost:3100")
        self._query = source.param("query", '{job=~".+"}')
        self._org_id = source.param("org_id")

    def run(self) -> None:
        self._running = True

        try:
            import asyncio

            asyncio.run(self._stream())
        except Exception as e:
            if self._running:
                self.signals.error_occurred.emit(f"Loki error: {e}")
                logger.warning("Loki tail error: %s", e)

        self.signals.status_changed.emit("disconnected")

    async def _stream(self) -> None:
        import websockets

        # Build WebSocket URL
        base = self._url.rstrip("/")
        if base.startswith("http://"):
            ws_url = "ws://" + base[7:]
        elif base.startswith("https://"):
            ws_url = "wss://" + base[8:]
        else:
            ws_url = "ws://" + base

        import urllib.parse

        ws_url += "/loki/api/v1/tail?" + urllib.parse.urlencode({"query": self._query})

        extra_headers = {}
        if self._org_id:
            extra_headers["X-Scope-OrgID"] = self._org_id

        logger.info("Connecting to Loki: %s", ws_url)

        async with websockets.connect(ws_url, additional_headers=extra_headers) as ws:
            self.signals.status_changed.emit("connected")
            logger.info("Loki WebSocket connected")

            async for raw in ws:
                if not self._running:
                    break
                try:
                    frame = json.loads(raw)
                    self._process_frame(frame)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug("Loki frame parse error: %s", e)

    def _process_frame(self, frame: dict) -> None:
        """Parse a Loki tail response frame."""
        streams = frame.get("streams", [])
        for stream in streams:
            labels = stream.get("stream", {})
            log_group = labels.get("job", labels.get("app", ""))
            for value in stream.get("values", []):
                # values are [timestamp_ns, line]
                if not isinstance(value, (list, tuple)) or len(value) < 2:
                    continue
                ts_ns = int(value[0])
                ts_ms = ts_ns // 1_000_000
                line = value[1]

                event = LogEvent(
                    timestamp=ts_ms,
                    message=line,
                    log_group=log_group,
                    level=detect_level(line),
                )
                self._buffer.push(event)
                self.signals.events_ready.emit()
