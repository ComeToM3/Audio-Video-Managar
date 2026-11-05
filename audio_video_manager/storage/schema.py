"""Schéma SQLite versionné."""

from __future__ import annotations

SCHEMA_VERSION = 4

SCHEMA_SQL_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disc_id TEXT,
    mbid TEXT,
    album_artist TEXT,
    album TEXT,
    year INTEGER,
    path TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    imported_at TEXT
);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_id INTEGER NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    title TEXT,
    path TEXT,
    duration_ms INTEGER,
    flac_ok INTEGER,
    rip_check_status TEXT,
    UNIQUE (release_id, number)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    step TEXT,
    workdir TEXT,
    started_at TEXT,
    updated_at TEXT,
    finished_at TEXT,
    error_summary TEXT,
    resume_token TEXT
);

CREATE TABLE IF NOT EXISTS job_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_releases_disc_id ON releases(disc_id);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_checkpoints_job ON job_checkpoints(job_id);
"""

SCHEMA_SQL_V2 = """
CREATE TABLE IF NOT EXISTS disc_metadata (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    approval TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS disc_metadata_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metadata_id TEXT NOT NULL REFERENCES disc_metadata(id) ON DELETE CASCADE,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    at TEXT NOT NULL,
    note TEXT,
    provenance TEXT
);

CREATE INDEX IF NOT EXISTS idx_disc_metadata_approval ON disc_metadata(approval);

-- Colonnes jobs ajoutées via migration Python si besoin (ALTER)
"""

SCHEMA_SQL_V3 = """
-- Colonnes archive jobs via migration Python ALTER
"""

SCHEMA_SQL_V4 = """
-- jobs.disc_id + index MBID (doublons AVM-06K) via migration Python ALTER
CREATE INDEX IF NOT EXISTS idx_releases_mbid ON releases(mbid);
CREATE INDEX IF NOT EXISTS idx_jobs_disc_id ON jobs(disc_id);
"""

# Conservé pour compat tests anciens imports
SCHEMA_SQL = SCHEMA_SQL_V1
