"""Tabbed source panel — one tab per connector with tree browsing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QAbstractItemModel, QModelIndex, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QStackedWidget, QTreeView, QVBoxLayout, QWidget

from logs_asmr.connectors import registry
from logs_asmr.connectors.base import ConnectorPlugin, SourceBrowser, SourceNode
from logs_asmr.ui import theme

if TYPE_CHECKING:
    from logs_asmr.db.database import Database
    from logs_asmr.models.source import Source

logger = logging.getLogger("logs_asmr.ui.source_panel")

_EMPTY_INDEX = QModelIndex()


# ---------------------------------------------------------------------------
# Generic tree model wrapping any SourceBrowser
# ---------------------------------------------------------------------------


class _BrowserNode:
    """Internal tree node wrapping a SourceNode."""

    __slots__ = ("source_node", "parent", "children", "fetched", "row_index")

    def __init__(
        self,
        source_node: SourceNode | None,
        parent: _BrowserNode | None = None,
    ) -> None:
        self.source_node = source_node
        self.parent = parent
        self.children: list[_BrowserNode] = []
        self.fetched = source_node is None  # root is pre-fetched
        self.row_index = 0

    @property
    def label(self) -> str:
        return self.source_node.label if self.source_node else ""


class _FetchSignals(QObject):
    finished = pyqtSignal(object, list)  # _BrowserNode, list[SourceNode]
    failed = pyqtSignal(object, str)


class _FetchWorker(QThread):
    """Background thread for fetching children from a SourceBrowser."""

    def __init__(
        self,
        browser: SourceBrowser,
        node: _BrowserNode,
        fetch_root: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.signals = _FetchSignals()
        self._browser = browser
        self._node = node
        self._fetch_root = fetch_root

    def run(self) -> None:
        try:
            if self._fetch_root:
                items = self._browser.fetch_root_nodes()
            else:
                items = self._browser.fetch_children(self._node.source_node)
            self.signals.finished.emit(self._node, items)
        except Exception as e:
            self.signals.failed.emit(self._node, str(e))


class GenericSourceModel(QAbstractItemModel):
    """Tree model wrapping any SourceBrowser instance."""

    def __init__(self, browser: SourceBrowser, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._browser = browser
        self._root = _BrowserNode(None)
        self._workers: list[_FetchWorker] = []

    def refresh(self) -> None:
        """Clear tree and fetch root nodes."""
        # Disconnect in-flight workers so stale results are dropped
        for worker in self._workers:
            worker.signals.finished.disconnect(self._on_children_fetched)
            worker.signals.failed.disconnect(self._on_fetch_failed)
        self.beginResetModel()
        self._root.children.clear()
        self._root.fetched = False
        self.endResetModel()
        self._fetch_root()

    def _fetch_root(self) -> None:
        worker = _FetchWorker(self._browser, self._root, fetch_root=True, parent=self)
        worker.signals.finished.connect(self._on_children_fetched)
        worker.signals.failed.connect(self._on_fetch_failed)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    # --- QAbstractItemModel interface ---

    def index(self, row: int, column: int, parent: QModelIndex = _EMPTY_INDEX) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = parent.internalPointer() if parent.isValid() else self._root
        if row < len(parent_node.children):
            return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: _BrowserNode = index.internalPointer()
        parent_node = node.parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row_index, 0, parent_node)

    def rowCount(self, parent: QModelIndex = _EMPTY_INDEX) -> int:
        node = parent.internalPointer() if parent.isValid() else self._root
        return len(node.children)

    def columnCount(self, parent: QModelIndex = _EMPTY_INDEX) -> int:
        return 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: ANN201
        if not index.isValid():
            return None
        node: _BrowserNode = index.internalPointer()
        if role == Qt.ItemDataRole.DisplayRole:
            return node.label
        return None

    def hasChildren(self, parent: QModelIndex = _EMPTY_INDEX) -> bool:
        node = parent.internalPointer() if parent.isValid() else self._root
        if node is self._root:
            return True
        # If not fetched yet, assume there could be children
        if not node.fetched:
            return True
        return len(node.children) > 0

    def canFetchMore(self, parent: QModelIndex) -> bool:
        if not parent.isValid():
            return False
        node: _BrowserNode = parent.internalPointer()
        return not node.fetched

    def fetchMore(self, parent: QModelIndex) -> None:
        if not parent.isValid():
            return
        node: _BrowserNode = parent.internalPointer()
        if node.fetched:
            return
        node.fetched = True
        self._fetch_children(node)

    def _fetch_children(self, node: _BrowserNode) -> None:
        worker = _FetchWorker(self._browser, node, parent=self)
        worker.signals.finished.connect(self._on_children_fetched)
        worker.signals.failed.connect(self._on_fetch_failed)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        self._workers.append(worker)
        worker.start()

    def _on_children_fetched(self, node: _BrowserNode, source_nodes: list[SourceNode]) -> None:
        if not source_nodes:
            return
        parent_idx = self._index_for_node(node)
        self.beginInsertRows(parent_idx, 0, len(source_nodes) - 1)
        for i, sn in enumerate(source_nodes):
            child = _BrowserNode(sn, parent=node)
            child.row_index = i
            node.children.append(child)
        self.endInsertRows()

    def _on_fetch_failed(self, node: _BrowserNode, error: str) -> None:
        logger.warning("Fetch failed for %s: %s", node.label, error)
        node.fetched = False

    def _cleanup_worker(self, worker: _FetchWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()

    def _index_for_node(self, node: _BrowserNode) -> QModelIndex:
        if node is self._root or node.parent is None:
            return QModelIndex()
        return self.createIndex(node.row_index, 0, node)

    def get_source_node(self, index: QModelIndex) -> SourceNode | None:
        """Return the SourceNode for a given model index."""
        if not index.isValid():
            return None
        node: _BrowserNode = index.internalPointer()
        return node.source_node


# ---------------------------------------------------------------------------
# Per-connector tab
# ---------------------------------------------------------------------------


class ConnectorSourceTab(QWidget):
    """A single tab for one connector — optional header + tree view."""

    source_selected = pyqtSignal(object)  # Source

    def __init__(self, plugin: ConnectorPlugin, db: Database | None = None, parent=None) -> None:
        super().__init__(parent)
        self._plugin = plugin
        self._db = db
        self._browser = plugin.browser_class(db)
        self._model = GenericSourceModel(self._browser, self)
        self._header_widget = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Optional header from browser
        self._header_widget = self._browser.create_header_widget(parent=self)
        if self._header_widget is not None:
            layout.addWidget(self._header_widget)

        # Tree view
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setStyleSheet(theme.tree_view_style())
        layout.addWidget(self._tree)

        self.setStyleSheet(theme.panel_background())

    def _connect_signals(self) -> None:
        self._tree.doubleClicked.connect(self._on_item_double_clicked)

        # If header widget has a refresh_requested signal, wire it to refresh tree
        if self._header_widget is not None:
            signal = getattr(self._header_widget, "refresh_requested", None)
            if signal is not None:
                signal.connect(self._refresh_tree)

    def _refresh_tree(self) -> None:
        self._model.refresh()

    def populate(self) -> None:
        """Initial population — triggers root node fetch."""
        self._model.refresh()

    def reload_browser(self) -> None:
        """Re-create the browser from DB prefs, rebuild header, and refresh tree."""
        self._browser = self._plugin.browser_class(self._db)
        self._model._browser = self._browser

        # Replace header widget
        layout = self.layout()
        if self._header_widget is not None:
            layout.removeWidget(self._header_widget)
            self._header_widget.deleteLater()
            self._header_widget = None

        new_header = self._browser.create_header_widget(parent=self)
        if new_header is not None:
            layout.insertWidget(0, new_header)
            self._header_widget = new_header
            signal = getattr(new_header, "refresh_requested", None)
            if signal is not None:
                signal.connect(self._refresh_tree)

        self._model.refresh()

    def _on_item_double_clicked(self, index: QModelIndex) -> None:
        source_node = self._model.get_source_node(index)
        if source_node is not None and source_node.is_selectable:
            source = self._browser.build_source(source_node)
            logger.info("Source selected: %s", source)
            self.source_selected.emit(source)


# ---------------------------------------------------------------------------
# Top-level source panel with connector dropdown
# ---------------------------------------------------------------------------


class SourcePanel(QWidget):
    """Source panel with a connector dropdown and per-connector browse tree."""

    source_selected = pyqtSignal(object)  # Source

    def __init__(self, db: Database | None = None, parent=None) -> None:
        super().__init__(parent)
        self._db = db
        self._connector_tabs: list[ConnectorSourceTab] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._combo = QComboBox()
        self._combo.setStyleSheet(theme.combo_style_with_margin())
        layout.addWidget(self._combo)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        self._combo.currentIndexChanged.connect(self._stack.setCurrentIndex)

        self.setMinimumWidth(160)
        self.setStyleSheet(theme.panel_background())

    def populate(self) -> None:
        """Discover connectors and create stacked pages."""
        registry.discover_and_register()
        plugins = registry.available_plugins()
        for plugin in plugins:
            tab = ConnectorSourceTab(plugin, db=self._db, parent=self)
            tab.source_selected.connect(self.source_selected.emit)
            self._connector_tabs.append(tab)
            self._combo.addItem(plugin.display_name)
            self._stack.addWidget(tab)
            tab.populate()

    def reload_browsers(self) -> None:
        """Re-create browsers from DB prefs and refresh trees (after settings change)."""
        for tab in self._connector_tabs:
            tab.reload_browser()
