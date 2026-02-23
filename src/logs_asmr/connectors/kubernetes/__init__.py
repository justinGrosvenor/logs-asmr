"""Kubernetes pod log connector."""

from __future__ import annotations


def register_plugin() -> None:
    from logs_asmr.connectors.base import ConnectorPlugin
    from logs_asmr.connectors.kubernetes.browser import KubernetesBrowser
    from logs_asmr.connectors.kubernetes.worker import KubernetesTailWorker
    from logs_asmr.connectors.registry import register

    register(
        ConnectorPlugin(
            connector_id="kubernetes",
            display_name="Kubernetes",
            browser_class=KubernetesBrowser,
            worker_class=KubernetesTailWorker,
            is_available=KubernetesBrowser.is_available(),
            missing_deps=KubernetesBrowser.missing_deps_message(),
        )
    )
