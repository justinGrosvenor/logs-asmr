"""Grafana Loki log connector."""

from __future__ import annotations


def register_plugin() -> None:
    from logs_asmr.connectors.base import ConnectorPlugin
    from logs_asmr.connectors.loki.browser import LokiBrowser
    from logs_asmr.connectors.loki.worker import LokiTailWorker
    from logs_asmr.connectors.registry import register

    register(
        ConnectorPlugin(
            connector_id="loki",
            display_name="Grafana Loki",
            browser_class=LokiBrowser,
            worker_class=LokiTailWorker,
            is_available=LokiBrowser.is_available(),
            missing_deps=LokiBrowser.missing_deps_message(),
        )
    )
