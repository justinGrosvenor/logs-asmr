"""Tests for database, preferences, and persistence."""

from __future__ import annotations

from pathlib import Path

from logs_asmr.db.database import (
    Database,
    get_bool_pref,
    get_int_pref,
    get_pref,
    set_pref,
)


def test_database_creates_tables(tmp_db: Database):
    tables = tmp_db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = {row["name"] for row in tables}
    assert "preferences" in names
    assert "recent_sources" in names
    assert "filter_presets" in names
    assert "schema_version" in names


def test_schema_version(tmp_db: Database):
    version = tmp_db.fetchone("SELECT MAX(version) as v FROM schema_version")
    assert version["v"] >= 1


def test_set_get_pref(tmp_db: Database):
    set_pref(tmp_db, "theme", "dark")
    assert get_pref(tmp_db, "theme") == "dark"


def test_get_pref_default(tmp_db: Database):
    assert get_pref(tmp_db, "nonexistent") is None
    assert get_pref(tmp_db, "nonexistent", "fallback") == "fallback"


def test_set_pref_overwrite(tmp_db: Database):
    set_pref(tmp_db, "key", "first")
    set_pref(tmp_db, "key", "second")
    assert get_pref(tmp_db, "key") == "second"


def test_get_bool_pref(tmp_db: Database):
    set_pref(tmp_db, "enabled", "true")
    assert get_bool_pref(tmp_db, "enabled") is True

    set_pref(tmp_db, "enabled", "false")
    assert get_bool_pref(tmp_db, "enabled") is False

    set_pref(tmp_db, "enabled", "1")
    assert get_bool_pref(tmp_db, "enabled") is True

    set_pref(tmp_db, "enabled", "yes")
    assert get_bool_pref(tmp_db, "enabled") is True


def test_get_bool_pref_default(tmp_db: Database):
    assert get_bool_pref(tmp_db, "missing") is False
    assert get_bool_pref(tmp_db, "missing", default=True) is True


def test_get_int_pref(tmp_db: Database):
    set_pref(tmp_db, "count", "42")
    assert get_int_pref(tmp_db, "count") == 42


def test_get_int_pref_invalid(tmp_db: Database):
    set_pref(tmp_db, "bad_int", "not_a_number")
    assert get_int_pref(tmp_db, "bad_int", default=99) == 99


def test_get_int_pref_default(tmp_db: Database):
    assert get_int_pref(tmp_db, "missing") == 0
    assert get_int_pref(tmp_db, "missing", default=10) == 10


def test_recent_sources_insert(tmp_db: Database):
    tmp_db.execute(
        "INSERT INTO recent_sources (connector, params_json, label) VALUES (?, ?, ?)",
        ("cloudwatch", '{"log_group":"/aws/lambda/my-func","region":"us-east-1"}', "my-func"),
    )
    rows = tmp_db.fetchall("SELECT * FROM recent_sources")
    assert len(rows) == 1
    assert rows[0]["connector"] == "cloudwatch"
    assert rows[0]["label"] == "my-func"


def test_recent_sources_unique_constraint(tmp_db: Database):
    params_json = '{"log_group":"/aws/lambda/my-func","region":"us-east-1"}'
    tmp_db.execute(
        "INSERT OR REPLACE INTO recent_sources (connector, params_json, label) "
        "VALUES (?, ?, ?)",
        ("cloudwatch", params_json, "my-func"),
    )
    tmp_db.execute(
        "INSERT OR REPLACE INTO recent_sources (connector, params_json, label) "
        "VALUES (?, ?, ?)",
        ("cloudwatch", params_json, "my-func"),
    )
    rows = tmp_db.fetchall("SELECT * FROM recent_sources")
    assert len(rows) == 1


def test_filter_presets_roundtrip(tmp_db: Database):
    tmp_db.execute(
        "INSERT INTO filter_presets (name, log_group, include_text, include_is_regex, "
        "exclude_text, exclude_is_regex, levels) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("errors-only", "/aws/lambda/api", "", 0, "", 0, "ERROR,WARN"),
    )
    row = tmp_db.fetchone("SELECT * FROM filter_presets WHERE name = ?", ("errors-only",))
    assert row is not None
    assert row["name"] == "errors-only"
    assert row["levels"] == "ERROR,WARN"
    assert row["log_group"] == "/aws/lambda/api"


def test_filter_presets_unique_by_name_and_group(tmp_db: Database):
    tmp_db.execute(
        "INSERT OR REPLACE INTO filter_presets (name, log_group, include_text) "
        "VALUES (?, ?, ?)",
        ("my-preset", "/group-a", "error"),
    )
    tmp_db.execute(
        "INSERT OR REPLACE INTO filter_presets (name, log_group, include_text) "
        "VALUES (?, ?, ?)",
        ("my-preset", "/group-a", "updated"),
    )
    rows = tmp_db.fetchall(
        "SELECT * FROM filter_presets WHERE name = ? AND log_group = ?",
        ("my-preset", "/group-a"),
    )
    assert len(rows) == 1
    assert rows[0]["include_text"] == "updated"


def test_database_from_nonexistent_path(tmp_path: Path):
    db_path = tmp_path / "subdir" / "nested" / "test.db"
    db = Database(db_path=db_path)
    assert db_path.exists()
    set_pref(db, "test", "value")
    assert get_pref(db, "test") == "value"
    db.close()


def test_database_close_and_reopen(tmp_db_path: Path):
    db1 = Database(db_path=tmp_db_path)
    set_pref(db1, "persist", "yes")
    db1.close()

    db2 = Database(db_path=tmp_db_path)
    assert get_pref(db2, "persist") == "yes"
    db2.close()
