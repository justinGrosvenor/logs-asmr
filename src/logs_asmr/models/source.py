"""Generic log source model — connector-agnostic."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Source:
    """Identifies a log source for any connector."""

    connector: str  # "cloudwatch", "docker", "file", etc.
    params: dict[str, str] = field(default_factory=dict)
    label: str = ""

    @property
    def display_name(self) -> str:
        return self.label or self.params.get("display_name", self.connector)

    def param(self, key: str, default: str = "") -> str:
        return self.params.get(key, default)
