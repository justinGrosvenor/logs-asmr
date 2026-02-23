"""Filter state data types."""

from __future__ import annotations

from dataclasses import dataclass, field

from logs_asmr.models.log_event import Level


@dataclass(slots=True)
class FilterState:
    """Current state of all filters."""

    include_text: str = ""
    include_is_regex: bool = False
    exclude_text: str = ""
    exclude_is_regex: bool = False
    levels: set[Level] = field(default_factory=lambda: set(Level))
    components: set[str] = field(default_factory=set)

    @property
    def is_default(self) -> bool:
        """True if no filters are active."""
        return (
            not self.include_text
            and not self.exclude_text
            and self.levels == set(Level)
            and not self.components
        )
