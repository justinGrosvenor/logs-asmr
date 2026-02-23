-- Migrate recent_sources to generic connector model
CREATE TABLE IF NOT EXISTS recent_sources_v2 (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    connector   TEXT NOT NULL DEFAULT 'cloudwatch',
    params_json TEXT NOT NULL DEFAULT '{}',
    label       TEXT DEFAULT '',
    used_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(connector, params_json)
);

INSERT OR IGNORE INTO recent_sources_v2 (connector, params_json, label, used_at)
SELECT 'cloudwatch',
    json_object('profile', profile, 'region', region,
                'log_group', log_group, 'log_stream', COALESCE(log_stream, '')),
    log_group || CASE WHEN log_stream != '' THEN ' / ' || log_stream ELSE '' END,
    used_at
FROM recent_sources;

DROP TABLE IF EXISTS recent_sources;
ALTER TABLE recent_sources_v2 RENAME TO recent_sources;

-- Add connector column to filter presets
ALTER TABLE filter_presets ADD COLUMN connector TEXT NOT NULL DEFAULT 'cloudwatch';
