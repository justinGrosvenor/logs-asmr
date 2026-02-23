-- Key-value store for app preferences and UI state
CREATE TABLE IF NOT EXISTS preferences (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);

-- Recently used log sources
CREATE TABLE IF NOT EXISTS recent_sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    profile     TEXT NOT NULL,
    region      TEXT NOT NULL,
    log_group   TEXT NOT NULL,
    log_stream  TEXT DEFAULT '',
    used_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(profile, region, log_group, log_stream)
);
CREATE INDEX IF NOT EXISTS idx_recent_sources_used ON recent_sources(used_at DESC);

-- Saved filter presets
CREATE TABLE IF NOT EXISTS filter_presets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    log_group       TEXT DEFAULT '',
    include_text    TEXT DEFAULT '',
    include_is_regex INTEGER DEFAULT 0,
    exclude_text    TEXT DEFAULT '',
    exclude_is_regex INTEGER DEFAULT 0,
    levels          TEXT DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, log_group)
);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
