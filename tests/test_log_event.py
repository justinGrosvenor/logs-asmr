"""Tests for log event models."""

from __future__ import annotations

from logs_asmr.models.log_event import (
    Level,
    LogEvent,
    detect_level,
    extract_component,
    extract_component_from_log_group,
)

# --- Level detection ---


def test_detect_error():
    assert detect_level("2024-01-01 ERROR something broke") == Level.ERROR


def test_detect_warn():
    assert detect_level("WARN: disk space low") == Level.WARN


def test_detect_warning_keyword():
    assert detect_level("[WARNING] retrying connection") == Level.WARN


def test_detect_debug():
    assert detect_level("DEBUG entering handler") == Level.DEBUG


def test_detect_info_default():
    assert detect_level("just a normal message") == Level.INFO


def test_detect_case_insensitive():
    assert detect_level("error in lowercase") == Level.ERROR


def test_detect_truncated_keywords():
    assert detect_level("ERRO: partial keyword") == Level.ERROR
    assert detect_level("DEBU trace enabled") == Level.DEBUG
    assert detect_level("DBG verbose") == Level.DEBUG


def test_detect_only_scans_first_80_chars():
    # ERROR beyond 80 chars should not be detected
    msg = "x" * 80 + " ERROR at the end"
    assert detect_level(msg) == Level.INFO


# --- Component extraction ---


def test_extract_component_json_service():
    msg = '{"service": "auth-svc", "msg": "login ok"}'
    assert extract_component(msg) == "auth-svc"


def test_extract_component_json_module():
    msg = '{"module": "payments", "msg": "charge"}'
    assert extract_component(msg) == "payments"


def test_extract_component_json_logger():
    msg = '{"logger": "com.example.App", "level": "INFO"}'
    assert extract_component(msg) == "com.example.App"


def test_extract_component_json_priority():
    # "service" should be checked before "component"
    msg = '{"service": "first", "component": "second"}'
    assert extract_component(msg) == "first"


def test_extract_component_non_json():
    assert extract_component("plain text log line") == ""


def test_extract_component_invalid_json():
    assert extract_component("{broken json") == ""


def test_extract_component_empty_string():
    assert extract_component("") == ""


def test_extract_component_json_no_known_field():
    msg = '{"unknown_field": "value", "msg": "hello"}'
    assert extract_component(msg) == ""


# --- Log group component extraction ---


def test_log_group_last_segment():
    assert extract_component_from_log_group("/aws/lambda/payment-service") == "payment-service"


def test_log_group_single_segment():
    assert extract_component_from_log_group("myapp") == "myapp"


def test_log_group_trailing_slash():
    assert extract_component_from_log_group("/aws/ecs/api-gateway/") == "api-gateway"


def test_log_group_empty():
    assert extract_component_from_log_group("") == ""


# --- LogEvent dataclass ---


def test_log_event_auto_detects_level():
    event = LogEvent(timestamp=1000, message="ERROR: failure")
    assert event.level == Level.ERROR


def test_log_event_preserves_explicit_level():
    event = LogEvent(timestamp=1000, message="ERROR: failure", level=Level.DEBUG)
    # Auto-detection only runs when level is INFO (default)
    assert event.level == Level.DEBUG


def test_log_event_auto_extracts_component():
    event = LogEvent(timestamp=1000, message='{"service": "auth", "msg": "ok"}')
    assert event.component == "auth"


def test_log_event_preserves_explicit_component():
    event = LogEvent(timestamp=1000, message='{"service": "auth"}', component="override")
    assert event.component == "override"


def test_display_line_format():
    event = LogEvent(timestamp=0, message="hello", level=Level.INFO)
    line = event.display_line
    assert "| INFO  | hello" in line
    assert "1970-01-01" in line


def test_display_line_cached():
    event = LogEvent(timestamp=0, message="hello")
    line1 = event.display_line
    line2 = event.display_line
    assert line1 is line2
