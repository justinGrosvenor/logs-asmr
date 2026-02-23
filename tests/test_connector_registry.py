"""Tests for the connector registry."""

from __future__ import annotations

import pytest

from logs_asmr.connectors.base import (
    ConnectorPlugin,
    SourceBrowser,
    SourceNode,
    TailWorker,
)
from logs_asmr.connectors import registry
from logs_asmr.models.source import Source


# ---------------------------------------------------------------------------
# Stubs for testing
# ---------------------------------------------------------------------------


class _StubBrowser(SourceBrowser):
    def connector_id(self) -> str:
        return "stub"

    def display_name(self) -> str:
        return "Stub"

    def fetch_root_nodes(self) -> list[SourceNode]:
        return []

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        return []

    def build_source(self, node: SourceNode) -> Source:
        return Source(connector="stub")


class _StubWorker(TailWorker):
    def run(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure each test starts with a clean registry."""
    saved = dict(registry._REGISTRY)
    registry._REGISTRY.clear()
    yield
    registry._REGISTRY.clear()
    registry._REGISTRY.update(saved)


class TestRegistry:
    def test_register_and_get(self):
        plugin = ConnectorPlugin(
            connector_id="stub",
            display_name="Stub",
            browser_class=_StubBrowser,
            worker_class=_StubWorker,
            is_available=True,
        )
        registry.register(plugin)
        assert registry.get_plugin("stub") is plugin

    def test_get_unknown_returns_none(self):
        assert registry.get_plugin("nonexistent") is None

    def test_available_plugins_filters(self):
        avail = ConnectorPlugin(
            connector_id="a",
            display_name="A",
            browser_class=_StubBrowser,
            worker_class=_StubWorker,
            is_available=True,
        )
        unavail = ConnectorPlugin(
            connector_id="b",
            display_name="B",
            browser_class=_StubBrowser,
            worker_class=_StubWorker,
            is_available=False,
            missing_deps="pip install b",
        )
        registry.register(avail)
        registry.register(unavail)

        available = registry.available_plugins()
        assert len(available) == 1
        assert available[0].connector_id == "a"

    def test_all_plugins_returns_everything(self):
        for cid, avail in [("x", True), ("y", False), ("z", True)]:
            registry.register(
                ConnectorPlugin(
                    connector_id=cid,
                    display_name=cid.upper(),
                    browser_class=_StubBrowser,
                    worker_class=_StubWorker,
                    is_available=avail,
                )
            )
        assert len(registry.all_plugins()) == 3

    def test_register_overwrites(self):
        p1 = ConnectorPlugin(
            connector_id="dup",
            display_name="V1",
            browser_class=_StubBrowser,
            worker_class=_StubWorker,
            is_available=True,
        )
        p2 = ConnectorPlugin(
            connector_id="dup",
            display_name="V2",
            browser_class=_StubBrowser,
            worker_class=_StubWorker,
            is_available=True,
        )
        registry.register(p1)
        registry.register(p2)
        assert registry.get_plugin("dup").display_name == "V2"
