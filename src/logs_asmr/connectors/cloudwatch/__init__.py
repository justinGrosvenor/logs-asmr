"""CloudWatch log connector."""

from __future__ import annotations


def register_plugin() -> None:
    from logs_asmr.connectors.base import ConnectorPlugin
    from logs_asmr.connectors.cloudwatch.browser import CloudWatchBrowser
    from logs_asmr.connectors.cloudwatch.worker import CloudWatchTailWorker
    from logs_asmr.connectors.registry import register

    register(
        ConnectorPlugin(
            connector_id="cloudwatch",
            display_name="AWS CloudWatch",
            browser_class=CloudWatchBrowser,
            worker_class=CloudWatchTailWorker,
            is_available=CloudWatchBrowser.is_available(),
            missing_deps=CloudWatchBrowser.missing_deps_message(),
        )
    )
