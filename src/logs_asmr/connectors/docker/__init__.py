"""Docker container log connector."""

from __future__ import annotations


def register_plugin() -> None:
    from logs_asmr.connectors.base import ConnectorPlugin
    from logs_asmr.connectors.docker.browser import DockerBrowser
    from logs_asmr.connectors.docker.worker import DockerTailWorker
    from logs_asmr.connectors.registry import register

    register(
        ConnectorPlugin(
            connector_id="docker",
            display_name="Docker",
            browser_class=DockerBrowser,
            worker_class=DockerTailWorker,
            is_available=DockerBrowser.is_available(),
            missing_deps=DockerBrowser.missing_deps_message(),
        )
    )
