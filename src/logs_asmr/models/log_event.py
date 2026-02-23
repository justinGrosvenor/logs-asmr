"""Log event data types."""

from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from datetime import UTC


class Level(enum.IntEnum):
    """Log severity levels, ordered by severity."""

    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


#: Lookup for level detection in log messages.
_LEVEL_KEYWORDS: dict[str, Level] = {
    "ERROR": Level.ERROR,
    "ERRO": Level.ERROR,
    "ERR": Level.ERROR,
    "WARN": Level.WARN,
    "WARNING": Level.WARN,
    "INFO": Level.INFO,
    "DEBUG": Level.DEBUG,
    "DEBU": Level.DEBUG,
    "DBG": Level.DEBUG,
}

#: Fields to check when extracting component from JSON logs.
_COMPONENT_FIELDS = ("service", "component", "module", "logger", "source")


@dataclass(slots=True)
class LogEvent:
    """A single log event from a log source."""

    timestamp: int  # epoch milliseconds
    message: str
    log_group: str = ""
    log_stream: str = ""
    level: Level = Level.INFO
    component: str = ""
    raw: str = ""

    #: Pre-formatted display line (cached).
    _display: str = field(default="", repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.level == Level.INFO and self.message:
            self.level = detect_level(self.message)
        if not self.component and self.message:
            self.component = extract_component(self.message)

    @property
    def display_line(self) -> str:
        """Formatted line for the log view."""
        if not self._display:
            from datetime import datetime

            ts = datetime.fromtimestamp(self.timestamp / 1000, tz=UTC)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S.") + f"{ts.microsecond // 1000:03d}"
            self._display = f"{ts_str} | {self.level.name:<5} | {self.message}"
        return self._display


def detect_level(message: str) -> Level:
    """Detect log level from message text."""
    upper = message[:80].upper()
    for keyword, level in _LEVEL_KEYWORDS.items():
        if keyword in upper:
            return level
    return Level.INFO


def extract_component(message: str) -> str:
    """Extract component/service name from a log message."""
    stripped = message.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                for field_name in _COMPONENT_FIELDS:
                    val = data.get(field_name)
                    if isinstance(val, str) and val:
                        return val
        except (json.JSONDecodeError, ValueError):
            pass
    return ""


def extract_component_from_log_group(log_group: str) -> str:
    """Extract component name from log group path (last segment)."""
    if not log_group:
        return ""
    parts = log_group.rstrip("/").split("/")
    return parts[-1] if parts else ""
