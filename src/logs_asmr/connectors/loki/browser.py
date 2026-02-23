"""Loki source browser — URL + LogQL query input."""

from __future__ import annotations

import logging
from urllib.parse import quote

from logs_asmr.connectors.base import SourceBrowser, SourceNode
from logs_asmr.models.source import Source
from logs_asmr.ui import theme

logger = logging.getLogger("logs_asmr.connectors.loki.browser")


class LokiBrowser(SourceBrowser):
    """Browse Loki labels and build LogQL tail sources."""

    def __init__(self, db=None) -> None:
        super().__init__(db)
        self._url = self._get_pref("url", "http://localhost:3100")
        self._query = self._get_pref("query", '{job=~".+"}')
        self._org_id = self._get_pref("org_id")

    def connector_id(self) -> str:
        return "loki"

    def display_name(self) -> str:
        return "Grafana Loki"

    def fetch_root_nodes(self) -> list[SourceNode]:
        """Fetch label values from Loki for browsing."""
        try:
            import httpx

            headers = {}
            if self._org_id:
                headers["X-Scope-OrgID"] = self._org_id

            resp = httpx.get(
                f"{self._url.rstrip('/')}/loki/api/v1/labels",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            labels = resp.json().get("data", [])
        except Exception as e:
            logger.warning("Cannot fetch Loki labels: %s", e)
            return []

        return [
            SourceNode(
                label=name,
                data={"label": name},
                node_type="label",
            )
            for name in sorted(labels)
            if name != "__name__"
        ]

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        """Fetch label values for a given label name."""
        if node.node_type != "label":
            return []
        label_name = node.data.get("label", "")
        try:
            import httpx

            headers = {}
            if self._org_id:
                headers["X-Scope-OrgID"] = self._org_id

            resp = httpx.get(
                f"{self._url.rstrip('/')}/loki/api/v1/label/{quote(label_name, safe='')}/values",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            values = resp.json().get("data", [])
        except Exception as e:
            logger.warning("Cannot fetch Loki label values for %s: %s", label_name, e)
            return []

        return [
            SourceNode(
                label=val,
                data={"label": label_name, "value": val},
                node_type="label_value",
                is_selectable=True,
            )
            for val in sorted(values)
        ]

    def build_source(self, node: SourceNode) -> Source:
        if node.node_type == "label_value":
            label = node.data.get("label", "").replace("\\", "\\\\").replace('"', '\\"')
            value = node.data.get("value", "").replace("\\", "\\\\").replace('"', '\\"')
            query = f'{{{label}="{value}"}}'
        else:
            query = self._query

        return Source(
            connector="loki",
            params={
                "url": self._url,
                "query": query,
                "org_id": self._org_id,
            },
            label=query,
        )

    def create_header_widget(self, parent=None):  # noqa: ANN201
        from PyQt6.QtWidgets import QLabel, QLineEdit, QVBoxLayout

        from logs_asmr.connectors.base import HeaderWidget

        widget = HeaderWidget(parent)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(2)

        url_label = QLabel("Loki URL")
        url_label.setStyleSheet(theme.label_style())
        layout.addWidget(url_label)

        url_input = QLineEdit()
        url_input.setText(self._url)

        def on_url_changed(t: str) -> None:
            self._url = t.strip()
            self._set_pref("url", self._url)

        url_input.textChanged.connect(on_url_changed)
        url_input.editingFinished.connect(widget.refresh_requested.emit)
        layout.addWidget(url_input)

        layout.addSpacing(4)

        query_label = QLabel("LogQL Query")
        query_label.setStyleSheet(theme.label_style())
        layout.addWidget(query_label)

        query_input = QLineEdit()
        query_input.setText(self._query)

        def on_query_changed(t: str) -> None:
            self._query = t.strip()
            self._set_pref("query", self._query)

        query_input.textChanged.connect(on_query_changed)
        layout.addWidget(query_input)

        layout.addSpacing(4)

        org_label = QLabel("Org ID (optional)")
        org_label.setStyleSheet(theme.label_style())
        layout.addWidget(org_label)

        org_input = QLineEdit()
        org_input.setPlaceholderText("X-Scope-OrgID for multi-tenant")
        org_input.setText(self._org_id)

        def on_org_changed(t: str) -> None:
            self._org_id = t.strip()
            self._set_pref("org_id", self._org_id)

        org_input.textChanged.connect(on_org_changed)
        layout.addWidget(org_input)

        return widget

    @classmethod
    def is_available(cls) -> bool:
        try:
            import httpx  # noqa: F401
            import websockets  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def missing_deps_message(cls) -> str:
        return "Install Loki deps: pip install logs-asmr[loki]"
