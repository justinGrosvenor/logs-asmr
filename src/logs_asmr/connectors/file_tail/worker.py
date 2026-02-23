"""FileTailWorker — tails a file or reads from stdin."""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import TYPE_CHECKING

from logs_asmr.connectors.base import TailWorker
from logs_asmr.models.log_event import LogEvent, detect_level

if TYPE_CHECKING:
    from PyQt6.QtCore import QObject

    from logs_asmr.models.source import Source
    from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.connectors.file_tail.worker")

_POLL_INTERVAL = 0.1  # 100ms


class FileTailWorker(TailWorker):
    """Tails a file (seek to end, poll for new lines) or reads stdin."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, source, parent)
        self._path = source.param("path", "-")
        self._encoding = source.param("encoding", "utf-8")

    def run(self) -> None:
        self._running = True
        if self._path == "-":
            self._tail_stdin()
        else:
            self._tail_file()
        self.signals.status_changed.emit("disconnected")

    def _tail_stdin(self) -> None:
        self.signals.status_changed.emit("connected")
        logger.info("Tailing stdin")
        for line in sys.stdin:
            if not self._running:
                break
            self._push_line(line.rstrip("\n"))

    def _tail_file(self) -> None:
        try:
            f = open(self._path, encoding=self._encoding, errors="replace")
        except FileNotFoundError:
            self.signals.error_occurred.emit(f"File not found: {self._path}")
            return
        except PermissionError:
            self.signals.error_occurred.emit(f"Permission denied: {self._path}")
            return

        try:
            # Seek to end
            f.seek(0, os.SEEK_END)
            self.signals.status_changed.emit("connected")
            logger.info("Tailing file: %s", self._path)

            inode = os.stat(self._path).st_ino

            while self._running:
                line = f.readline()
                if line:
                    self._push_line(line.rstrip("\n"))
                    continue

                # No new data — check for file rotation
                try:
                    new_inode = os.stat(self._path).st_ino
                    if new_inode != inode:
                        logger.info("File rotated, reopening: %s", self._path)
                        f.close()
                        f = open(self._path, encoding=self._encoding, errors="replace")
                        inode = new_inode
                        continue
                except (FileNotFoundError, PermissionError):
                    pass

                time.sleep(_POLL_INTERVAL)
        finally:
            f.close()

    def _push_line(self, line: str) -> None:
        if not line:
            return
        event = LogEvent(
            timestamp=int(time.time() * 1000),
            message=line,
            log_group=self._path,
            level=detect_level(line),
        )
        self._buffer.push(event)
        self.signals.events_ready.emit()
