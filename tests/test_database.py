from __future__ import annotations

from pathlib import Path

from audio_video_manager.storage import SCHEMA_VERSION, Database


def test_initialize_schema(avm_home: Path) -> None:
    db_path = avm_home / "test.sqlite3"
    with Database(db_path) as db:
        version = db.initialize()
        assert version == SCHEMA_VERSION
        assert db.get_schema_version() == SCHEMA_VERSION

        conn = db.connect()
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "releases" in tables
        assert "tracks" in tables
        assert "jobs" in tables
        assert "job_checkpoints" in tables
        assert "schema_migrations" in tables
        assert "videos" in tables


def test_initialize_idempotent(avm_home: Path) -> None:
    db_path = avm_home / "idem.sqlite3"
    db = Database(db_path)
    db.initialize()
    db.initialize()
    assert db.get_schema_version() == SCHEMA_VERSION
    db.close()


def test_video_migration_preserves_existing_releases(avm_home: Path) -> None:
    db = Database(avm_home / "migration.sqlite3")
    db.initialize()
    conn = db.connect()
    conn.execute("INSERT INTO releases(album, path) VALUES (?, ?)", ("Album", "local"))
    conn.execute("DELETE FROM schema_migrations WHERE version = 5")
    conn.execute("DROP TABLE videos")
    conn.commit()
    assert db.initialize() == SCHEMA_VERSION
    assert conn.execute("SELECT album FROM releases").fetchone()[0] == "Album"
    assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == 0
    db.close()
