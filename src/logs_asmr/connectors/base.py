"""Abstract base classes for log source connectors."""

from __future__ import annotations

import abc
import dataclasses
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from logs_asmr.db.database import Database
    from logs_asmr.models.source import Source
    from logs_asmr.streaming.ring_buffer import RingBuffer

logger = logging.getLogger("logs_asmr.connectors.base")


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


class TailSignals(QObject):
    """Signals emitted by all tail workers."""

    events_ready = pyqtSignal()
    status_changed = pyqtSignal(str)  # "connected", "disconnected", "reconnecting"
    error_occurred = pyqtSignal(str)


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------


class TailWorker(QThread):
    """Abstract base for all streaming workers.

    Subclasses implement ``run()`` to stream log events into the ring buffer.
    The downstream pipeline (EventProcessor, AudioManager) consumes events via
    ``signals.events_ready`` and the shared ``RingBuffer``.
    """

    def __init__(
        self,
        ring_buffer: RingBuffer,
        source: Source,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.signals = TailSignals()
        self._buffer = ring_buffer
        self._source = source
        self._running = False

    @abc.abstractmethod
    def run(self) -> None: ...

    def stop(self) -> None:
        self._running = False


# ---------------------------------------------------------------------------
# Source browser
# ---------------------------------------------------------------------------


class HeaderWidget(QWidget):
    """Header widget with a signal to request tree refresh."""

    refresh_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)


class SourceNode:
    """Tree node for source browsing."""

    __slots__ = ("label", "data", "node_type", "children_fetched", "is_selectable", "children")

    def __init__(
        self,
        label: str,
        data: dict[str, str],
        node_type: str,
        is_selectable: bool = False,
    ) -> None:
        self.label = label
        self.data = data
        self.node_type = node_type
        self.is_selectable = is_selectable
        self.children_fetched = False
        self.children: list[SourceNode] = []


class SourceBrowser(abc.ABC):
    """Abstract base for source discovery UI."""

    def __init__(self, db: Database | None = None) -> None:
        self._db = db

    def _get_pref(self, key: str, default: str = "") -> str:
        if self._db is None:
            return default
        from logs_asmr.db.database import get_pref

        val = get_pref(self._db, f"connector.{self.connector_id()}.{key}")
        return val if val is not None else default

    def _set_pref(self, key: str, value: str) -> None:
        if self._db is None:
            return
        from logs_asmr.db.database import set_pref

        set_pref(self._db, f"connector.{self.connector_id()}.{key}", value)

    @abc.abstractmethod
    def connector_id(self) -> str: ...

    @abc.abstractmethod
    def display_name(self) -> str: ...

    @abc.abstractmethod
    def fetch_root_nodes(self) -> list[SourceNode]: ...

    @abc.abstractmethod
    def fetch_children(self, node: SourceNode) -> list[SourceNode]: ...

    @abc.abstractmethod
    def build_source(self, node: SourceNode) -> Source: ...

    def create_header_widget(self, parent: QObject | None = None):  # noqa: ANN201
        """Optional per-connector header widget (e.g. profile/region combos)."""
        return None

    def has_settings(self) -> bool:
        # Overridden by subclasses; base returns True when a header widget exists,
        # since create_settings_widget falls back to it.
        return type(self).create_header_widget is not SourceBrowser.create_header_widget

    def create_settings_widget(self, parent: QObject | None = None):  # noqa: ANN201
        return self.create_header_widget(parent)

    @classmethod
    def is_available(cls) -> bool:
        return True

    @classmethod
    def missing_deps_message(cls) -> str:
        return ""


# ---------------------------------------------------------------------------
# Plugin record
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ConnectorPlugin:
    connector_id: str
    display_name: str
    browser_class: type[SourceBrowser]
    worker_class: type[TailWorker]
    is_available: bool
    missing_deps: str = ""


# ---------------------------------------------------------------------------
# Generic exception
# ---------------------------------------------------------------------------


class ConnectorError(Exception):
    """Base exception for connector errors with user-facing message."""

    def __init__(self, user_message: str, detail: str = "") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail
