"""GCP Cloud Logging connector."""

from __future__ import annotations


def register_plugin() -> None:
    from logs_asmr.connectors.base import ConnectorPlugin
    from logs_asmr.connectors.gcp.browser import GCPBrowser
    from logs_asmr.connectors.gcp.worker import GCPTailWorker
    from logs_asmr.connectors.registry import register

    register(
        ConnectorPlugin(
            connector_id="gcp",
            display_name="GCP Cloud Logging",
            browser_class=GCPBrowser,
            worker_class=GCPTailWorker,
            is_available=GCPBrowser.is_available(),
            missing_deps=GCPBrowser.missing_deps_message(),
        )
    )
