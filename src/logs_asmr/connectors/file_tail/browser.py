"""File tail source browser — file picker + path input."""

from __future__ import annotations

import logging

from logs_asmr.connectors.base import SourceBrowser, SourceNode
from logs_asmr.models.source import Source

logger = logging.getLogger("logs_asmr.connectors.file_tail.browser")


class FileTailBrowser(SourceBrowser):
    """Browse and select log files for tailing."""

    def __init__(self, db=None) -> None:
        super().__init__(db)
        self._path = ""

    def connector_id(self) -> str:
        return "file"

    def display_name(self) -> str:
        return "File / stdin"

    def fetch_root_nodes(self) -> list[SourceNode]:
        # Stdin is always available
        return [
            SourceNode(
                label="stdin (pipe input)",
                data={"path": "-"},
                node_type="file",
                is_selectable=True,
            )
        ]

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        return []

    def build_source(self, node: SourceNode) -> Source:
        path = node.data.get("path", "-")
        label = path if path != "-" else "stdin"
        return Source(
            connector="file",
            params={"path": path},
            label=label,
        )

    def create_header_widget(self, parent=None):  # noqa: ANN201
        from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

        widget = QWidget(parent)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(4)

        path_input = QLineEdit()
        path_input.setPlaceholderText("Enter file path or use Browse...")
        layout.addWidget(path_input)

        browse_btn = QPushButton("Browse...")

        def on_browse() -> None:
            path, _ = QFileDialog.getOpenFileName(widget, "Select Log File")
            if path:
                path_input.setText(path)
                self._path = path

        browse_btn.clicked.connect(on_browse)
        layout.addWidget(browse_btn)

        def on_path_changed(text: str) -> None:
            self._path = text

        path_input.textChanged.connect(on_path_changed)
        widget.path_input = path_input

        return widget

    def has_settings(self) -> bool:
        return False

    @classmethod
    def is_available(cls) -> bool:
        return True
