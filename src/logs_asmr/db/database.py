"""Thread-safe SQLite database with WAL mode and migration support."""

import logging
import sqlite3
import threading
from pathlib import Path

from logs_asmr.constants import DB_PATH

logger = logging.getLogger("logs_asmr.db")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    """Thread-safe SQLite database with WAL mode and migration support."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = str(db_path or DB_PATH)
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._all_conns: list[sqlite3.Connection] = []
        self._conns_lock = threading.Lock()
        self._closed = False

        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_conn()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        self._run_migrations()
        logger.info("Database initialized at %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local connection."""
        if self._closed:
            raise RuntimeError("Database has been closed")
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
            with self._conns_lock:
                self._all_conns.append(conn)
        return self._local.conn

    @staticmethod
    def _is_read_only(sql: str) -> bool:
        """Check if a SQL statement is read-only (SELECT / WITH ... SELECT / EXPLAIN)."""
        # Strip leading whitespace and SQL comments
        s = sql.lstrip()
        while s.startswith("--") or s.startswith("/*"):
            if s.startswith("--"):
                newline = s.find("\n")
                s = s[newline + 1 :].lstrip() if newline >= 0 else ""
            else:
                end = s.find("*/")
                s = s[end + 2 :].lstrip() if end >= 0 else ""
        keyword = s.split(None, 1)[0].upper() if s else ""
        return keyword in ("SELECT", "WITH", "EXPLAIN", "PRAGMA")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a SQL statement with write serialization."""
        conn = self._get_conn()
        if self._is_read_only(sql):
            return conn.execute(sql, params)
        with self._write_lock:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor

    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor:
        """Execute a SQL statement with multiple parameter sets."""
        conn = self._get_conn()
        with self._write_lock:
            cursor = conn.executemany(sql, params_list)
            conn.commit()
            return cursor

    def executescript(self, sql: str) -> None:
        """Execute a SQL script (multiple statements)."""
        conn = self._get_conn()
        with self._write_lock:
            conn.executescript(sql)

    def fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute a SELECT and return one row."""
        return self._get_conn().execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a SELECT and return all rows."""
        return self._get_conn().execute(sql, params).fetchall()

    def _run_migrations(self) -> None:
        """Apply pending migrations in order."""
        conn = self._get_conn()

        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        conn.commit()

        current = self._get_schema_version()

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for migration_file in migration_files:
            version = int(migration_file.stem.split("_")[0])
            if version > current:
                logger.info("Applying migration %03d: %s", version, migration_file.name)
                sql = migration_file.read_text()
                with self._write_lock:
                    conn.executescript(sql)
                    conn.execute(
                        "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                        (version,),
                    )
                    conn.commit()

    def _get_schema_version(self) -> int:
        """Get the current schema version."""
        row = self._get_conn().execute("SELECT MAX(version) as v FROM schema_version").fetchone()
        return row["v"] if row and row["v"] is not None else 0

    def close(self) -> None:
        """Close all thread-local connections."""
        self._closed = True
        with self._conns_lock:
            for conn in self._all_conns:
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_conns.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None


# Preferences helpers


def get_pref(db: Database, key: str, default: str | None = None) -> str | None:
    """Get a preference value by key."""
    row = db.fetchone("SELECT value FROM preferences WHERE key = ?", (key,))
    return row["value"] if row else default


def set_pref(db: Database, key: str, value: str) -> None:
    """Set a preference value."""
    db.execute(
        "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
        (key, value),
    )


def get_bool_pref(db: Database, key: str, default: bool = False) -> bool:
    """Get a boolean preference."""
    val = get_pref(db, key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")


def get_int_pref(db: Database, key: str, default: int = 0) -> int:
    """Get an integer preference."""
    val = get_pref(db, key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default
