"""Fake log generator using the TailWorker interface."""

from __future__ import annotations

import logging
import random
import time

from PyQt6.QtCore import QObject

from logs_asmr.connectors.base import TailWorker
from logs_asmr.models.log_event import Level, LogEvent
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.fake_tail")

_COMPONENTS = ["auth-service", "api-gateway", "payment", "user-mgmt", "notifications"]

_MESSAGES = {
    Level.ERROR: [
        "Connection refused to database host db-primary.internal:5432",
        "Unhandled exception in request handler: NullPointerException",
        "Circuit breaker OPEN for downstream service payment-api",
        "Out of memory: heap space exhausted after 2048MB allocation",
        "TLS handshake failed: certificate expired 2h ago",
        "Request timeout after 30000ms waiting for response from inventory-service",
    ],
    Level.WARN: [
        "Retry attempt 3/5 for message publish to queue orders.pending",
        "Response time 2847ms exceeds threshold of 2000ms for /api/v2/checkout",
        "Cache miss rate 34% exceeds alert threshold of 25%",
        "Connection pool 87% utilized (87/100 connections)",
        "Rate limit approaching: 450/500 requests in current window",
        "Deprecated API endpoint called: /api/v1/users (removal: 2025-06-01)",
    ],
    Level.INFO: [
        "Request completed: POST /api/v2/orders 201 Created (145ms)",
        "User authenticated: user_id=u-38291 method=oauth2 provider=google",
        "Deployment rolling-update started: version=2.14.7 replicas=3/5",
        "Health check passed: all 4 dependencies healthy",
        "Cache warmed: 12847 entries loaded from snapshot in 3.2s",
        "Batch job completed: processed 1847 records in 12.4s (149/s)",
        "WebSocket connection established: client_id=ws-8827",
        "Configuration reloaded: 3 values changed, 0 errors",
    ],
    Level.DEBUG: [
        "SQL query executed in 2.3ms: SELECT * FROM orders WHERE status = 'pending'",
        "HTTP request: GET /internal/health -> 200 (1ms)",
        "Message dequeued from orders.pending: msg_id=m-774829",
        "Token validation: sub=u-38291 exp=1707264000 iat=1707177600",
        "Feature flag evaluated: enable_new_checkout=true for segment=beta_users",
    ],
}

_FAKE_SOURCE = Source(connector="fake", params={"mode": "demo"}, label="Demo (fake)")


class FakeTailWorker(TailWorker):
    """Generates fake log events at a configurable rate."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        events_per_second: float = 50.0,
        error_ratio: float = 0.02,
        warn_ratio: float = 0.08,
        debug_ratio: float = 0.30,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, _FAKE_SOURCE, parent)
        self._rate = events_per_second
        self._error_ratio = error_ratio
        self._warn_ratio = warn_ratio
        self._debug_ratio = debug_ratio

    def run(self) -> None:
        self._running = True
        self.signals.status_changed.emit("connected")
        logger.info("Fake tail started at %.1f events/sec", self._rate)

        interval = 1.0 / self._rate if self._rate > 0 else 0.1
        batch_size = max(1, int(self._rate * 0.1))  # batch per 100ms

        while self._running:
            events = []
            for _ in range(batch_size):
                event = self._generate_event()
                events.append(event)

            self._buffer.push_batch(events)
            self.signals.events_ready.emit()
            time.sleep(interval * batch_size)

        self.signals.status_changed.emit("disconnected")

    def _generate_event(self) -> LogEvent:
        r = random.random()
        if r < self._error_ratio:
            level = Level.ERROR
        elif r < self._error_ratio + self._warn_ratio:
            level = Level.WARN
        elif r < self._error_ratio + self._warn_ratio + self._debug_ratio:
            level = Level.DEBUG
        else:
            level = Level.INFO

        message = random.choice(_MESSAGES[level])
        component = random.choice(_COMPONENTS)
        timestamp = int(time.time() * 1000)

        return LogEvent(
            timestamp=timestamp,
            message=message,
            level=level,
            component=component,
            log_group="fake/demo-service",
            log_stream="fake-stream-001",
        )
