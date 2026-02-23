"""DockerTailWorker — streams container logs via docker SDK."""

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

logger = logging.getLogger("logs_asmr.connectors.docker.worker")


class DockerTailWorker(TailWorker):
    """Streams log output from a Docker container."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, source, parent)
        self._container_id = source.param("container_id")
        self._container_name = source.param("container_name", self._container_id)

    def run(self) -> None:
        self._running = True

        try:
            import docker

            client = docker.from_env()
            container = client.containers.get(self._container_id)
        except Exception as e:
            self.signals.error_occurred.emit(f"Cannot connect to Docker: {e}")
            self.signals.status_changed.emit("disconnected")
            return

        self.signals.status_changed.emit("connected")
        logger.info("Tailing Docker container: %s", self._container_name)

        try:
            for chunk in container.logs(stream=True, follow=True, tail=0):
                if not self._running:
                    break
                for line in chunk.decode("utf-8", errors="replace").splitlines():
                    if not line:
                        continue
                    event = LogEvent(
                        timestamp=int(time.time() * 1000),
                        message=line,
                        log_group=self._container_name,
                        level=detect_level(line),
                    )
                    self._buffer.push(event)
                    self.signals.events_ready.emit()
        except Exception as e:
            if self._running:
                self.signals.error_occurred.emit(f"Docker stream error: {e}")
                logger.warning("Docker tail error: %s", e)
        finally:
            try:
                client.close()
            except Exception:
                pass

        self.signals.status_changed.emit("disconnected")
