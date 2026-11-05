"""Accès SQLite minimal avec versionnement et migrations."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from audio_video_manager.logging_setup import get_logger
from audio_video_manager.paths import default_db_path
from audio_video_manager.storage.schema import (
    SCHEMA_SQL_V1,
    SCHEMA_SQL_V2,
    SCHEMA_SQL_V4,
    SCHEMA_VERSION,
)

log = get_logger("storage")

__all__ = ["Database", "SCHEMA_VERSION"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_db_path()
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def initialize(self) -> int:
        """Applique le schéma jusqu'à SCHEMA_VERSION."""
        conn = self.connect()
        conn.executescript(SCHEMA_SQL_V1)
        current = self.get_schema_version()
        if current is None:
            # Nouvelle DB : poser v1 puis migrer vers courant
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, _utc_now()),
            )
            conn.commit()
            current = 1
            log.info("Schéma SQLite initialisé v1 → %s", self.path)

        if current < 2:
            self._migrate_to_v2(conn)
            current = 2

        if current < 3:
            self._migrate_to_v3(conn)
            current = 3

        if current < 4:
            self._migrate_to_v4(conn)
            current = 4

        if current < SCHEMA_VERSION:
            raise RuntimeError(
                f"Migration manquante : DB v{current} → v{SCHEMA_VERSION}"
            )
        log.debug("Schéma à jour v%s", current)
        return SCHEMA_VERSION

    def _migrate_to_v2(self, conn: sqlite3.Connection) -> None:
        log.info("Migration SQLite v1 → v2 (disc_metadata)")
        conn.executescript(SCHEMA_SQL_V2)
        # Enrichir jobs
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
        }
        if "mode" not in cols:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN mode TEXT NOT NULL DEFAULT 'technical_test'"
            )
        if "metadata_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN metadata_id TEXT")
        if "publish_allowed" not in cols:
            conn.execute(
                "ALTER TABLE jobs ADD COLUMN publish_allowed INTEGER NOT NULL DEFAULT 0"
            )
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (2, _utc_now()),
        )
        conn.commit()

    def _migrate_to_v3(self, conn: sqlite3.Connection) -> None:
        log.info("Migration SQLite v2 → v3 (archive jobs)")
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
        }
        alters = [
            ("selected_release_mbid", "ALTER TABLE jobs ADD COLUMN selected_release_mbid TEXT"),
            ("collision_policy", "ALTER TABLE jobs ADD COLUMN collision_policy TEXT"),
            ("warnings_json", "ALTER TABLE jobs ADD COLUMN warnings_json TEXT"),
            ("library_path", "ALTER TABLE jobs ADD COLUMN library_path TEXT"),
        ]
        for name, sql in alters:
            if name not in cols:
                conn.execute(sql)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (3, _utc_now()),
        )
        conn.commit()

    def _migrate_to_v4(self, conn: sqlite3.Connection) -> None:
        log.info("Migration SQLite v3 → v4 (garde-fous doublons)")
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
        }
        if "disc_id" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN disc_id TEXT")
        # Indexes (SCHEMA_SQL_V4) — safe si jobs.disc_id vient d’être ajouté
        conn.executescript(SCHEMA_SQL_V4)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (4, _utc_now()),
        )
        conn.commit()

    def get_schema_version(self) -> int | None:
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM schema_migrations"
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None or row["v"] is None:
            return None
        return int(row["v"])
