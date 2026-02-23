"""File tail log connector."""

from __future__ import annotations


def register_plugin() -> None:
    from logs_asmr.connectors.base import ConnectorPlugin
    from logs_asmr.connectors.file_tail.browser import FileTailBrowser
    from logs_asmr.connectors.file_tail.worker import FileTailWorker
    from logs_asmr.connectors.registry import register

    register(
        ConnectorPlugin(
            connector_id="file",
            display_name="File / stdin",
            browser_class=FileTailBrowser,
            worker_class=FileTailWorker,
            is_available=True,
        )
    )
