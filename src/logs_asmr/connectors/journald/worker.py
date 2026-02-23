"""JournaldTailWorker — follows journalctl --output=json via subprocess."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from typing import TYPE_CHECKING

from logs_asmr.connectors.base import TailWorker
from logs_asmr.models.log_event import Level, LogEvent

if TYPE_CHECKING:
    from PyQt6.QtCore import QObject

    from logs_asmr.models.source import Source
    from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.connectors.journald.worker")

_PRIORITY_MAP = {
    0: Level.ERROR,  # emerg
    1: Level.ERROR,  # alert
    2: Level.ERROR,  # crit
    3: Level.ERROR,  # err
    4: Level.WARN,   # warning
    5: Level.INFO,   # notice
    6: Level.INFO,   # info
    7: Level.DEBUG,  # debug
}


class JournaldTailWorker(TailWorker):
    """Streams journal entries via journalctl subprocess."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, source, parent)
        self._unit = source.param("unit")
        self._identifier = source.param("identifier")
        self._boot = source.param("boot", "0")

    def run(self) -> None:
        self._running = True

        cmd = [
            "journalctl",
            "--follow",
            "--output=json",
            "--no-pager",
            f"--boot={self._boot}",
        ]
        if self._unit:
            cmd.append(f"--unit={self._unit}")
        if self._identifier:
            cmd.append(f"SYSLOG_IDENTIFIER={self._identifier}")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError:
            self.signals.error_occurred.emit("journalctl not found in PATH")
            self.signals.status_changed.emit("disconnected")
            return
        except Exception as e:
            self.signals.error_occurred.emit(f"Cannot start journalctl: {e}")
            self.signals.status_changed.emit("disconnected")
            return

        self.signals.status_changed.emit("connected")
        logger.info("Tailing journald: %s", " ".join(cmd))

        try:
            for line in proc.stdout:
                if not self._running:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    self._process_entry(entry)
                except (json.JSONDecodeError, KeyError):
                    # Non-JSON output — emit as-is
                    event = LogEvent(
                        timestamp=int(time.time() * 1000),
                        message=line,
                        log_group="journald",
                    )
                    self._buffer.push(event)
                    self.signals.events_ready.emit()
        except Exception as e:
            if self._running:
                self.signals.error_occurred.emit(f"journald error: {e}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        self.signals.status_changed.emit("disconnected")

    def _process_entry(self, entry: dict) -> None:
        """Parse a JSON journal entry."""
        # Timestamp: __REALTIME_TIMESTAMP is microseconds since epoch
        ts_us = int(entry.get("__REALTIME_TIMESTAMP", time.time() * 1_000_000))
        ts_ms = ts_us // 1000

        # Message: may be a string or a byte array
        message = entry.get("MESSAGE", "")
        if isinstance(message, list):
            # Byte array representation
            message = bytes(message).decode("utf-8", errors="replace")

        # Source info
        unit = entry.get("_SYSTEMD_UNIT", "")
        identifier = entry.get("SYSLOG_IDENTIFIER", "")

        # Priority
        priority = int(entry.get("PRIORITY", 6))
        level = _PRIORITY_MAP.get(priority, Level.INFO)

        event = LogEvent(
            timestamp=ts_ms,
            message=message,
            log_group=unit or "journald",
            log_stream=identifier,
            level=level,
            component=identifier,
        )
        self._buffer.push(event)
        self.signals.events_ready.emit()
