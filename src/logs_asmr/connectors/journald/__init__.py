"""systemd journald log connector (Linux only)."""

from __future__ import annotations


def register_plugin() -> None:
    from logs_asmr.connectors.base import ConnectorPlugin
    from logs_asmr.connectors.journald.browser import JournaldBrowser
    from logs_asmr.connectors.journald.worker import JournaldTailWorker
    from logs_asmr.connectors.registry import register

    register(
        ConnectorPlugin(
            connector_id="journald",
            display_name="journald",
            browser_class=JournaldBrowser,
            worker_class=JournaldTailWorker,
            is_available=JournaldBrowser.is_available(),
            missing_deps=JournaldBrowser.missing_deps_message(),
        )
    )
