"""Tests for database migration 002 — connector refactor."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from logs_asmr.db.database import Database


class TestMigration002:
    """Verify migration 002 preserves CloudWatch data in the new schema."""

    def test_old_data_migrated(self, tmp_path: Path):
        """Insert data using the old schema (migration 001), then let migration 002 run."""
        db_path = tmp_path / "test_migration.db"

        # Manually apply migration 001 only
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        migration_001 = (
            Path(__file__).parent.parent
            / "src"
            / "logs_asmr"
            / "db"
            / "migrations"
            / "001_initial.sql"
        )
        conn.executescript(migration_001.read_text())
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (1,)
        )

        # Insert old-format data
        conn.execute(
            "INSERT INTO recent_sources (profile, region, log_group, log_stream, used_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("default", "us-east-1", "/app/web", "stream-1", "2025-01-15 10:00:00"),
        )
        conn.execute(
            "INSERT INTO recent_sources (profile, region, log_group, log_stream, used_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("prod", "eu-west-1", "/app/api", "", "2025-01-16 12:00:00"),
        )
        conn.commit()
        conn.close()

        # Now open via Database — this triggers migration 002
        db = Database(db_path=db_path)
        try:
            # Verify schema version is now 2
            row = db.fetchone("SELECT MAX(version) as v FROM schema_version")
            assert row["v"] == 2

            # Verify data was migrated
            rows = db.fetchall(
                "SELECT connector, params_json, label, used_at FROM recent_sources "
                "ORDER BY used_at"
            )
            assert len(rows) == 2

            # First row: has log_stream
            r0 = rows[0]
            assert r0["connector"] == "cloudwatch"
            params0 = json.loads(r0["params_json"])
            assert params0["profile"] == "default"
            assert params0["region"] == "us-east-1"
            assert params0["log_group"] == "/app/web"
            assert params0["log_stream"] == "stream-1"
            assert r0["label"] == "/app/web / stream-1"

            # Second row: no log_stream
            r1 = rows[1]
            assert r1["connector"] == "cloudwatch"
            params1 = json.loads(r1["params_json"])
            assert params1["profile"] == "prod"
            assert params1["region"] == "eu-west-1"
            assert params1["log_group"] == "/app/api"
            assert params1["log_stream"] == ""
            assert r1["label"] == "/app/api"
        finally:
            db.close()

    def test_filter_presets_gets_connector_column(self, tmp_path: Path):
        """Verify migration 002 adds connector column to filter_presets."""
        db_path = tmp_path / "test_migration_presets.db"

        # Apply migration 001 only
        conn = sqlite3.connect(str(db_path))
        migration_001 = (
            Path(__file__).parent.parent
            / "src"
            / "logs_asmr"
            / "db"
            / "migrations"
            / "001_initial.sql"
        )
        conn.executescript(migration_001.read_text())
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
        conn.execute(
            "INSERT INTO filter_presets (name, log_group, include_text) "
            "VALUES (?, ?, ?)",
            ("errors-only", "/app/web", "ERROR"),
        )
        conn.commit()
        conn.close()

        # Trigger migration 002
        db = Database(db_path=db_path)
        try:
            row = db.fetchone("SELECT connector FROM filter_presets WHERE name = ?", ("errors-only",))
            assert row["connector"] == "cloudwatch"
        finally:
            db.close()

    def test_fresh_db_has_both_migrations(self, tmp_path: Path):
        """A fresh database applies all migrations cleanly."""
        db = Database(db_path=tmp_path / "fresh.db")
        try:
            row = db.fetchone("SELECT MAX(version) as v FROM schema_version")
            assert row["v"] == 2

            # Verify new schema columns exist
            db.execute(
                "INSERT INTO recent_sources (connector, params_json, label) "
                "VALUES (?, ?, ?)",
                ("file", '{"path": "/tmp/test.log"}', "/tmp/test.log"),
            )
            rows = db.fetchall("SELECT * FROM recent_sources")
            assert len(rows) == 1
        finally:
            db.close()
