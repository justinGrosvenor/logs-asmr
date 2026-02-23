"""Tests for the generic Source model."""

from __future__ import annotations

from logs_asmr.models.source import Source


class TestSource:
    def test_display_name_uses_label(self):
        s = Source(connector="cloudwatch", params={"log_group": "/app"}, label="My App")
        assert s.display_name == "My App"

    def test_display_name_falls_back_to_display_name_param(self):
        s = Source(connector="docker", params={"display_name": "web-1"})
        assert s.display_name == "web-1"

    def test_display_name_falls_back_to_connector(self):
        s = Source(connector="file")
        assert s.display_name == "file"

    def test_param_returns_value(self):
        s = Source(connector="cloudwatch", params={"profile": "prod", "region": "us-east-1"})
        assert s.param("profile") == "prod"
        assert s.param("region") == "us-east-1"

    def test_param_returns_default(self):
        s = Source(connector="file", params={"path": "/var/log/syslog"})
        assert s.param("encoding", "utf-8") == "utf-8"
        assert s.param("missing") == ""

    def test_default_params_empty_dict(self):
        s = Source(connector="fake")
        assert s.params == {}
        assert s.label == ""

    def test_param_priority_label_over_display_name(self):
        s = Source(connector="docker", params={"display_name": "fallback"}, label="primary")
        assert s.display_name == "primary"

    def test_slots(self):
        s = Source(connector="test")
        assert hasattr(s, "__slots__") or hasattr(type(s), "__slots__")
