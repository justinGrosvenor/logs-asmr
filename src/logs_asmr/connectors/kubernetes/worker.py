"""KubernetesTailWorker — streams pod logs via kubernetes SDK."""

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

logger = logging.getLogger("logs_asmr.connectors.kubernetes.worker")


class KubernetesTailWorker(TailWorker):
    """Streams log output from a Kubernetes pod container."""

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(ring_buffer, source, parent)
        self._context = source.param("context")
        self._namespace = source.param("namespace", "default")
        self._pod = source.param("pod")
        self._container = source.param("container")

    def run(self) -> None:
        self._running = True

        try:
            from kubernetes import client, config, watch

            # Use new_client_from_config for an isolated ApiClient — avoids
            # mutating the global default Configuration (thread-unsafe).
            kwargs = {}
            if self._context:
                kwargs["context"] = self._context
            api_client = config.new_client_from_config(**kwargs)
            v1 = client.CoreV1Api(api_client=api_client)
        except Exception as e:
            self.signals.error_occurred.emit(f"Cannot connect to Kubernetes: {e}")
            self.signals.status_changed.emit("disconnected")
            return

        self.signals.status_changed.emit("connected")
        log_group = f"{self._namespace}/{self._pod}"
        logger.info("Tailing K8s pod: %s/%s", log_group, self._container)

        w = watch.Watch()
        try:
            kwargs = {
                "name": self._pod,
                "namespace": self._namespace,
                "follow": True,
                "tail_lines": 0,
                "_preload_content": False,
            }
            if self._container:
                kwargs["container"] = self._container

            for line in w.stream(v1.read_namespaced_pod_log, **kwargs):
                if not self._running:
                    break
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = line.rstrip("\n")
                if not line:
                    continue
                event = LogEvent(
                    timestamp=int(time.time() * 1000),
                    message=line,
                    log_group=log_group,
                    log_stream=self._container,
                    level=detect_level(line),
                )
                self._buffer.push(event)
                self.signals.events_ready.emit()
        except Exception as e:
            if self._running:
                self.signals.error_occurred.emit(f"Kubernetes stream error: {e}")
                logger.warning("K8s tail error: %s", e)
        finally:
            w.stop()

        self.signals.status_changed.emit("disconnected")
