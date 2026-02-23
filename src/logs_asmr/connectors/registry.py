"""Connector plugin registry — discover and manage log source connectors."""

from __future__ import annotations

import importlib
import logging

from logs_asmr.connectors.base import ConnectorPlugin

logger = logging.getLogger("logs_asmr.connectors.registry")

_REGISTRY: dict[str, ConnectorPlugin] = {}


def register(plugin: ConnectorPlugin) -> None:
    """Register a connector plugin."""
    _REGISTRY[plugin.connector_id] = plugin
    logger.info(
        "Registered connector: %s (available=%s)", plugin.connector_id, plugin.is_available
    )


def get_plugin(connector_id: str) -> ConnectorPlugin | None:
    """Get a plugin by connector ID."""
    return _REGISTRY.get(connector_id)


def available_plugins() -> list[ConnectorPlugin]:
    """Return all registered plugins that are available (dependencies installed)."""
    return [p for p in _REGISTRY.values() if p.is_available]


def all_plugins() -> list[ConnectorPlugin]:
    """Return all registered plugins, including unavailable ones."""
    return list(_REGISTRY.values())


def discover_and_register() -> None:
    """Import each connector module and call its register_plugin()."""
    for module_name in [
        "logs_asmr.connectors.cloudwatch",
        "logs_asmr.connectors.file_tail",
        "logs_asmr.connectors.docker",
        "logs_asmr.connectors.kubernetes",
        "logs_asmr.connectors.gcp",
        "logs_asmr.connectors.loki",
        "logs_asmr.connectors.journald",
    ]:
        try:
            mod = importlib.import_module(module_name)
            mod.register_plugin()
        except ImportError:
            logger.debug("Connector %s not available (missing module)", module_name)
        except Exception:
            logger.warning("Failed to register connector %s", module_name, exc_info=True)
