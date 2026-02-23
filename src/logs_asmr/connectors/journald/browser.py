"""journald source browser — lists systemd units."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys

from logs_asmr.connectors.base import SourceBrowser, SourceNode
from logs_asmr.models.source import Source

logger = logging.getLogger("logs_asmr.connectors.journald.browser")


class JournaldBrowser(SourceBrowser):
    """Browse systemd journal units."""

    def __init__(self, db=None) -> None:
        super().__init__(db)

    def connector_id(self) -> str:
        return "journald"

    def display_name(self) -> str:
        return "journald"

    def fetch_root_nodes(self) -> list[SourceNode]:
        """List systemd service units."""
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--output=json", "--no-pager"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.warning("systemctl failed: %s", result.stderr)
                return []
            units = json.loads(result.stdout)
        except Exception as e:
            logger.warning("Cannot list systemd units: %s", e)
            return []

        nodes = [
            SourceNode(
                label="(all units)",
                data={"unit": ""},
                node_type="unit",
                is_selectable=True,
            )
        ]
        for unit in units:
            name = unit.get("unit", "")
            if not name:
                continue
            nodes.append(
                SourceNode(
                    label=name,
                    data={"unit": name},
                    node_type="unit",
                    is_selectable=True,
                )
            )
        return nodes

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        return []

    def build_source(self, node: SourceNode) -> Source:
        unit = node.data.get("unit", "")
        return Source(
            connector="journald",
            params={"unit": unit, "boot": "0"},
            label=unit or "journald (all)",
        )

    @classmethod
    def is_available(cls) -> bool:
        return sys.platform == "linux" and shutil.which("journalctl") is not None

    @classmethod
    def missing_deps_message(cls) -> str:
        return "journald is only available on Linux with systemd"
