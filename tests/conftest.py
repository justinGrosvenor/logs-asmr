"""Shared test fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Headless Qt for CI
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture()
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def tmp_db(tmp_db_path: Path):
    from logs_asmr.db.database import Database

    db = Database(db_path=tmp_db_path)
    yield db
    db.close()
