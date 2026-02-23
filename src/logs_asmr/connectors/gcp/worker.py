"""GCPTailWorker — polls GCP Cloud Logging for new entries."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from logs_asmr.connectors.base import TailWorker
from logs_asmr.models.log_event import LogEvent, detect_level

if TYPE_CHECKING:
    from PyQt6.QtCore import QObject

    from logs_asmr.models.source import Source
    from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.connectors.gcp.worker")

_POLL_INTERVAL = 2.0  # seconds


class GCPTailWorker(TailWorker):
    """Polls GCP Cloud Logging for new log entries."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, source, parent)
        self._project = source.param("project")
        self._log_name = source.param("log_name")
        self._filter = source.param("filter")

    def run(self) -> None:
        self._running = True

        try:
            from google.cloud import logging as gcp_logging

            client = gcp_logging.Client(project=self._project)
        except Exception as e:
            self.signals.error_occurred.emit(f"Cannot connect to GCP: {e}")
            self.signals.status_changed.emit("disconnected")
            return

        self.signals.status_changed.emit("connected")
        logger.info("Tailing GCP project=%s log=%s", self._project, self._log_name)

        last_timestamp = None

        try:
            while self._running:
                # Build filter
                parts = []
                if self._log_name:
                    parts.append(f'logName="projects/{self._project}/logs/{self._log_name}"')
                if self._filter:
                    parts.append(self._filter)
                if last_timestamp:
                    parts.append(f'timestamp>"{last_timestamp}"')

                filter_str = " AND ".join(parts) if parts else None

                try:
                    entries = list(
                        client.list_entries(
                            filter_=filter_str,
                            order_by="timestamp asc",
                            page_size=100,
                        )
                    )
                except Exception as e:
                    logger.warning("GCP poll error: %s", e)
                    time.sleep(_POLL_INTERVAL)
                    continue

                for entry in entries:
                    ts_ms = int(entry.timestamp.timestamp() * 1000) if entry.timestamp else int(
                        time.time() * 1000
                    )
                    message = str(entry.payload) if entry.payload else ""
                    resource_type = (
                        entry.resource.type if entry.resource else ""
                    )
                    event = LogEvent(
                        timestamp=ts_ms,
                        message=message,
                        log_group=resource_type,
                        log_stream=entry.log_name or "",
                        level=detect_level(message),
                    )
                    self._buffer.push(event)
                    self.signals.events_ready.emit()
                    if entry.timestamp:
                        last_timestamp = entry.timestamp.isoformat()

                time.sleep(_POLL_INTERVAL)
        except Exception as e:
            if self._running:
                self.signals.error_occurred.emit(f"GCP stream error: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass

        self.signals.status_changed.emit("disconnected")
