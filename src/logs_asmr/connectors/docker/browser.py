"""Docker source browser — lists running containers."""

from __future__ import annotations

import logging

from logs_asmr.connectors.base import SourceBrowser, SourceNode
from logs_asmr.models.source import Source

logger = logging.getLogger("logs_asmr.connectors.docker.browser")


class DockerBrowser(SourceBrowser):
    """Browse running Docker containers."""

    def __init__(self, db=None) -> None:
        super().__init__(db)

    def connector_id(self) -> str:
        return "docker"

    def display_name(self) -> str:
        return "Docker"

    def fetch_root_nodes(self) -> list[SourceNode]:
        try:
            import docker

            client = docker.from_env()
            containers = client.containers.list()
        except Exception as e:
            logger.warning("Cannot list Docker containers: %s", e)
            return []

        nodes = []
        for c in containers:
            name = c.name or c.short_id
            nodes.append(
                SourceNode(
                    label=f"{name} ({c.short_id})",
                    data={"container_id": c.id, "container_name": name},
                    node_type="container",
                    is_selectable=True,
                )
            )
        return nodes

    def fetch_children(self, node: SourceNode) -> list[SourceNode]:
        return []

    def build_source(self, node: SourceNode) -> Source:
        return Source(
            connector="docker",
            params={
                "container_id": node.data.get("container_id", ""),
                "container_name": node.data.get("container_name", ""),
            },
            label=node.data.get("container_name", ""),
        )

    @classmethod
    def is_available(cls) -> bool:
        try:
            import docker  # noqa: F401

            return True
        except ImportError:
            return False

    @classmethod
    def missing_deps_message(cls) -> str:
        return "Install docker SDK: pip install logs-asmr[docker]"
