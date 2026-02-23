"""GCP Cloud Logging source browser."""

from __future__ import annotations

import logging

from logs_asmr.connectors.base import SourceBrowser, SourceNode
from logs_asmr.models.source import Source
from logs_asmr.ui import theme

logger = logging.getLogger("logs_asmr.connectors.gcp.browser")


class GCPBrowser(SourceBrowser):
    """Browse GCP Cloud Logging resources."""

    def __init__(self, db=None) -> None:
        super().__init__(db)
        self._project = self._get_pref("project")

    def connector_id(self) -> str:
        return "gcp"

    def display_name(self) -> str:
        return "GCP Cloud Logging"

    def fetch_root_nodes(self) -> list[SourceNode]:
        if not self._project:
            return []
        try:
            from google.cloud import logging as gcp_logging

            client = gcp_logging.Client(project=self._project)

            # Use the dedicated list_logs API when available (returns log names directly,
            # much more efficient than scanning entries).
            resource_name = f"projects/{self._project}"
            log_names = [
                name for name in client.logging_api.list_logs(resource_name, max_results=500)
            ]
        except Exception as e:
            logger.warning("Cannot list GCP log names: %s", e)
            return []

        return [
            SourceNode(
                label=name,
                data={"log_name": name},
                node_type="log_name",
                is_selectable=True,
            )
            for name in sorted(log_names)
        ]

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        return []

    def build_source(self, node: SourceNode) -> Source:
        return Source(
            connector="gcp",
            params={
                "project": self._project,
                "log_name": node.data.get("log_name", ""),
            },
            label=node.data.get("log_name", ""),
        )

    def create_header_widget(self, parent=None):  # noqa: ANN201
        from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout

        from logs_asmr.connectors.base import HeaderWidget

        widget = HeaderWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(2)

        proj_label = QLabel("Project ID")
        proj_label.setStyleSheet(theme.label_style())
        layout.addWidget(proj_label)

        project_input = QLineEdit()
        project_input.setPlaceholderText("my-gcp-project")

        def on_project_changed(text: str) -> None:
            self._project = text.strip()
            self._set_pref("project", self._project)

        project_input.textChanged.connect(on_project_changed)
        project_input.editingFinished.connect(widget.refresh_requested.emit)
        layout.addWidget(project_input)

        # Restore from DB or auto-detect from gcloud (off the UI thread)
        if self._project:
            project_input.setText(self._project)
        else:
            import threading

            def _detect_project() -> None:
                try:
                    import subprocess

                    result = subprocess.run(
                        ["gcloud", "config", "get-value", "project"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        project = result.stdout.strip()
                        # Schedule UI update on main thread
                        from PyQt6.QtCore import QTimer

                        QTimer.singleShot(0, lambda: project_input.setText(project))
                except Exception:
                    pass

            threading.Thread(target=_detect_project, daemon=True).start()

        return widget

    @classmethod
    def is_available(cls) -> bool:
        try:
            import google.cloud.logging  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def missing_deps_message(cls) -> str:
        return "Install GCP SDK: pip install logs-asmr[gcp]"
