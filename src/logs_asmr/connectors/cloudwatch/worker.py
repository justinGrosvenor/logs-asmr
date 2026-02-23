"""CloudWatchTailWorker — streams CloudWatch Live Tail in a background QThread."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import boto3

from logs_asmr.connectors.base import TailWorker
from logs_asmr.connectors.cloudwatch.errors import translate_error
from logs_asmr.constants import MAX_RECONNECT_ATTEMPTS, RECONNECT_BACKOFF_SECONDS
from logs_asmr.models.log_event import LogEvent, detect_level

if TYPE_CHECKING:
    from PyQt6.QtCore import QObject

    from logs_asmr.models.source import Source
    from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.connectors.cloudwatch.worker")


class CloudWatchTailWorker(TailWorker):
    """Streams CloudWatch Live Tail events into a ring buffer.

    Runs in a dedicated thread. The responseStream iterator blocks, so this
    must not run on the main thread.
    """

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        filter_pattern: str = "",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, source, parent)
        self._filter_pattern = filter_pattern
        self._reconnect_count = 0

    def run(self) -> None:
        self._running = True
        self._reconnect_count = 0

        while self._running:
            try:
                self._stream()
            except Exception as e:
                if not self._running:
                    break

                user_msg, detail = translate_error(e)
                logger.warning("Live tail error: %s", detail)

                self._reconnect_count += 1
                if self._reconnect_count > MAX_RECONNECT_ATTEMPTS:
                    self.signals.error_occurred.emit(user_msg)
                    self.signals.status_changed.emit("disconnected")
                    break

                self.signals.status_changed.emit("reconnecting")
                logger.info(
                    "Reconnecting (attempt %d/%d) in %.1fs",
                    self._reconnect_count,
                    MAX_RECONNECT_ATTEMPTS,
                    RECONNECT_BACKOFF_SECONDS,
                )
                time.sleep(RECONNECT_BACKOFF_SECONDS)

        self.signals.status_changed.emit("disconnected")

    def _stream(self) -> None:
        """Open a Live Tail session and iterate events."""
        profile = self._source.param("profile")
        region = self._source.param("region")
        log_group = self._source.param("log_group")
        log_stream = self._source.param("log_stream")
        log_group_arn = self._source.param("log_group_arn")

        session = boto3.Session(
            profile_name=profile,
            region_name=region,
        )
        client = session.client("logs")

        # logGroupIdentifiers requires ARNs, not names
        log_group_id = log_group_arn or log_group
        kwargs: dict = {
            "logGroupIdentifiers": [log_group_id],
        }
        if log_stream:
            kwargs["logStreamNames"] = [log_stream]
        if self._filter_pattern:
            kwargs["logEventFilterPattern"] = self._filter_pattern

        logger.info("Starting live tail: %s", kwargs)
        response = client.start_live_tail(**kwargs)
        event_stream = response["responseStream"]

        self.signals.status_changed.emit("connected")
        self._reconnect_count = 0  # Reset on successful connection

        try:
            for event in event_stream:
                if not self._running:
                    break

                if "sessionStart" in event:
                    session_id = event["sessionStart"].get("sessionId", "unknown")
                    logger.info("Live tail session started: %s", session_id)
                    continue

                if "sessionUpdate" in event:
                    update = event["sessionUpdate"]

                    # Check for sampling
                    metadata = update.get("sessionMetadata", {})
                    if metadata.get("sampled", False):
                        self.signals.status_changed.emit("sampling")

                    # Process log events
                    log_events = update.get("sessionResults", [])
                    if log_events:
                        parsed = []
                        for le in log_events:
                            parsed.append(
                                LogEvent(
                                    timestamp=le.get("timestamp", int(time.time() * 1000)),
                                    message=le.get("message", "").rstrip("\n"),
                                    log_group=le.get("logGroupIdentifier", log_group),
                                    log_stream=le.get("logStreamName", ""),
                                    level=detect_level(le.get("message", "")),
                                    raw=str(le),
                                )
                            )
                        self._buffer.push_batch(parsed)
                        self.signals.events_ready.emit()
        finally:
            import contextlib

            with contextlib.suppress(Exception):
                event_stream.close()
            with contextlib.suppress(Exception):
                client.close()

    def update_filter_pattern(self, pattern: str) -> None:
        """Update the server-side filter pattern (requires reconnect)."""
        self._filter_pattern = pattern
