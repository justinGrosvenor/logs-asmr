"""Tests for the filter engine."""

from __future__ import annotations

from logs_asmr.models.filter_state import FilterState
from logs_asmr.models.log_event import Level, LogEvent
from logs_asmr.streaming.filter_engine import FilterEngine


def _event(msg: str = "test", level: Level = Level.INFO, component: str = "") -> LogEvent:
    return LogEvent(timestamp=1000, message=msg, level=level, component=component)


def test_empty_filter_passes_all():
    fe = FilterEngine()
    fe.update(FilterState())
    assert fe.matches(_event("anything"))


def test_include_text():
    fe = FilterEngine()
    fe.update(FilterState(include_text="error"))
    assert fe.matches(_event("An error occurred"))
    assert not fe.matches(_event("All is fine"))


def test_include_case_insensitive():
    fe = FilterEngine()
    fe.update(FilterState(include_text="ERROR"))
    assert fe.matches(_event("an error happened"))


def test_exclude_text():
    fe = FilterEngine()
    fe.update(FilterState(exclude_text="health"))
    assert not fe.matches(_event("health check ok"))
    assert fe.matches(_event("error occurred"))


def test_include_regex():
    fe = FilterEngine()
    fe.update(FilterState(include_text=r"err\w+", include_is_regex=True))
    assert fe.matches(_event("An error occurred"))
    assert not fe.matches(_event("All fine"))


def test_exclude_regex():
    fe = FilterEngine()
    fe.update(FilterState(exclude_text=r"health\s*check", exclude_is_regex=True))
    assert not fe.matches(_event("health check passed"))
    assert fe.matches(_event("deployment started"))


def test_invalid_regex_fallback():
    fe = FilterEngine()
    fe.update(FilterState(include_text="[invalid", include_is_regex=True))
    # Falls back to literal match
    assert fe.matches(_event("contains [invalid bracket"))
    assert not fe.matches(_event("no match here"))


def test_level_filter():
    fe = FilterEngine()
    fe.update(FilterState(levels={Level.ERROR, Level.WARN}))
    assert fe.matches(_event("test", Level.ERROR))
    assert fe.matches(_event("test", Level.WARN))
    assert not fe.matches(_event("test", Level.INFO))
    assert not fe.matches(_event("test", Level.DEBUG))


def test_component_filter():
    fe = FilterEngine()
    fe.update(FilterState(components={"auth-service"}))
    assert fe.matches(_event("test", component="auth-service"))
    assert not fe.matches(_event("test", component="api-gateway"))
    # Events without component pass when components filter is active
    assert fe.matches(_event("test", component=""))


def test_combined_filters():
    fe = FilterEngine()
    fe.update(
        FilterState(
            include_text="timeout",
            exclude_text="health",
            levels={Level.ERROR, Level.WARN},
        )
    )
    assert fe.matches(_event("timeout occurred", Level.ERROR))
    assert not fe.matches(_event("timeout occurred", Level.INFO))  # level filtered
    assert not fe.matches(_event("health check timeout", Level.ERROR))  # excluded
    assert not fe.matches(_event("all fine", Level.ERROR))  # no include match


def test_filter_batch():
    fe = FilterEngine()
    fe.update(FilterState(levels={Level.ERROR}))
    events = [
        _event("err1", Level.ERROR),
        _event("info1", Level.INFO),
        _event("err2", Level.ERROR),
    ]
    result = fe.filter_batch(events)
    assert len(result) == 2
    assert result[0].message == "err1"
    assert result[1].message == "err2"


def test_default_filter_passes_all():
    fe = FilterEngine()
    fe.update(FilterState())
    events = [_event(f"msg{i}") for i in range(100)]
    result = fe.filter_batch(events)
    assert len(result) == 100
