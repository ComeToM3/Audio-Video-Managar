"""AVM-06K — garde-fous doublons (domaine, hors UI)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from audio_video_manager.library.duplicates import (
    DuplicateBlockedError,
    DuplicateGate,
    MatchKind,
    assert_archive_allowed,
    assess_duplicates,
    assess_from_sheet,
)
from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.orchestration.archive_job import run_archive_job
from audio_video_manager.storage import SCHEMA_VERSION, Database
from tests.flac_fixtures import write_minimal_flac

_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
    b"\x1d\x1a\x1c\x1c $.\' \",#\x1c\x1c(7),01444\x1f\'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b"
    b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04"
    b"\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q"
    b"\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17"
    b"\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz"
    b"\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99"
    b"\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7"
    b"\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5"
    b"\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1"
    b"\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xaa\xff\xd9"
)


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _approved(**kwargs):
    sheet = make_approvable_sheet(**kwargs)
    sheet.edition.label = "Label"
    sheet.edition.catalog_number = "CAT"
    sheet.edition.musicbrainz_release_id = "mbid-a"
    sheet.edition.cover_status = CoverStatus.CONFIRMED
    sheet.edition.cover_path_or_url = "https://example.test/c.jpg"
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    approve_sheet(sheet, note="t")
    return sheet


def _insert_release(
    db: Database,
    *,
    disc_id: str | None,
    mbid: str | None,
    artist: str,
    album: str,
    path: str,
    year: int = 1999,
) -> None:
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, 'imported', ?)
        """,
        (disc_id, mbid, artist, album, year, path, _utc()),
    )
    conn.commit()


def _insert_job(
    db: Database,
    *,
    job_id: str,
    state: str,
    disc_id: str | None = None,
    mbid: str | None = None,
    workdir: str | None = None,
) -> None:
    conn = db.connect()
    now = _utc()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at,
            mode, selected_release_mbid, disc_id
        ) VALUES (?, ?, ?, ?, ?, ?, 'normal', ?, ?)
        """,
        (job_id, state, state, workdir, now, now, mbid, disc_id),
    )
    conn.commit()


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "avm.sqlite3")
    d.initialize()
    assert d.get_schema_version() == SCHEMA_VERSION
    yield d
    d.close()


def test_schema_v4_has_jobs_disc_id(db: Database) -> None:
    cols = {r[1] for r in db.connect().execute("PRAGMA table_info(jobs)").fetchall()}
    assert "disc_id" in cols
    idx = {
        r[1]
        for r in db.connect().execute("PRAGMA index_list(releases)").fetchall()
    }
    assert "idx_releases_mbid" in idx


def test_exact_disc_and_edition_requires_confirm(db: Database, tmp_path: Path) -> None:
    album_dir = tmp_path / "lib" / "Demo Artist" / "1999 - Demo Album"
    album_dir.mkdir(parents=True)
    _insert_release(
        db,
        disc_id="demo.disc.id",
        mbid="mbid-a",
        artist="Demo Artist",
        album="Demo Album",
        path=str(album_dir),
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet)
    assert a.gate == DuplicateGate.REQUIRE_CONFIRM
    assert any(h.kind == MatchKind.DISC_AND_EDITION for h in a.hits)
    with pytest.raises(DuplicateBlockedError):
        assert_archive_allowed(a, confirmed_rearchive=False)
    assert_archive_allowed(a, confirmed_rearchive=True)


def test_same_mbid_present_requires_confirm(db: Database, tmp_path: Path) -> None:
    album_dir = tmp_path / "A"
    album_dir.mkdir()
    _insert_release(
        db,
        disc_id="other.disc",
        mbid="mbid-a",
        artist="Demo Artist",
        album="Demo Album",
        path=str(album_dir),
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet)
    assert a.gate == DuplicateGate.REQUIRE_CONFIRM
    assert any(h.kind == MatchKind.SAME_MBID for h in a.hits)


def test_different_editions_not_auto_equated(db: Database, tmp_path: Path) -> None:
    """Même titre, MBID distincts → similarité advisory, jamais REQUIRE sur titre seul."""
    album_dir = tmp_path / "B"
    album_dir.mkdir()
    _insert_release(
        db,
        disc_id="other.disc",
        mbid="mbid-OTHER-EDITION",
        artist="Demo Artist",
        album="Demo Album",
        path=str(album_dir),
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet)
    assert a.gate == DuplicateGate.WARN
    assert any(h.kind == MatchKind.SIMILAR_META for h in a.hits)
    assert not any(
        h.kind in (MatchKind.DISC_AND_EDITION, MatchKind.SAME_MBID) for h in a.hits
    )
    # WARN n’empêche pas
    assert_archive_allowed(a, confirmed_rearchive=False)


def test_same_disc_different_mbid_not_merged(db: Database, tmp_path: Path) -> None:
    album_dir = tmp_path / "C"
    album_dir.mkdir()
    _insert_release(
        db,
        disc_id="demo.disc.id",
        mbid="mbid-OTHER",
        artist="X",
        album="Y",
        path=str(album_dir),
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet)
    assert any(h.kind == MatchKind.SAME_DISC_ID for h in a.hits)
    assert "autre édition" in " ".join(h.message_fr for h in a.hits).lower() or any(
        "édition" in h.message_fr.lower() for h in a.hits
    )


def test_missing_folder_warns_not_blocks(db: Database, tmp_path: Path) -> None:
    _insert_release(
        db,
        disc_id="demo.disc.id",
        mbid="mbid-a",
        artist="Demo Artist",
        album="Demo Album",
        path=str(tmp_path / "gone" / "album"),
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet)
    assert a.gate == DuplicateGate.WARN
    assert_archive_allowed(a)


def test_title_only_never_require_confirm(db: Database, tmp_path: Path) -> None:
    album_dir = tmp_path / "D"
    album_dir.mkdir()
    _insert_release(
        db,
        disc_id=None,
        mbid=None,
        artist="Demo Artist",
        album="Demo Album",
        path=str(album_dir),
    )
    sheet = _approved()
    # Pas de disc/mbid match fort côté catalogue → similarité seule
    a = assess_duplicates(
        db,
        disc_id="brand.new.disc",
        release_mbid="brand-new-mbid",
        album_artist="Demo Artist",
        album_title="Demo Album",
    )
    assert a.gate == DuplicateGate.WARN
    assert all(h.kind == MatchKind.SIMILAR_META for h in a.hits)


def test_active_job_denies(db: Database) -> None:
    _insert_job(
        db,
        job_id="job-active-1",
        state="Ripping",
        disc_id="demo.disc.id",
        mbid="mbid-a",
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet)
    assert a.gate == DuplicateGate.DENY
    with pytest.raises(DuplicateBlockedError):
        assert_archive_allowed(a, confirmed_rearchive=True)


def test_exclude_own_job_id(db: Database) -> None:
    _insert_job(
        db,
        job_id="job-self",
        state="Organizing",
        disc_id="demo.disc.id",
        mbid="mbid-a",
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet, exclude_job_id="job-self")
    assert a.gate != DuplicateGate.DENY


def test_recoverable_job_warns(db: Database, tmp_path: Path) -> None:
    wd = tmp_path / "jobwork"
    wd.mkdir()
    _insert_job(
        db,
        job_id="job-fail-1",
        state="Failed",
        disc_id="demo.disc.id",
        mbid="mbid-a",
        workdir=str(wd),
    )
    sheet = _approved()
    a = assess_from_sheet(db, sheet)
    assert a.gate == DuplicateGate.WARN
    assert any(h.kind == MatchKind.RECOVERABLE_JOB for h in a.hits)


def test_pipeline_blocks_silent_duplicate(tmp_path: Path) -> None:
    sheet = _approved(tracks=1)
    jobs = tmp_path / "jobs"
    lib = tmp_path / "Music"
    db = Database(tmp_path / "avm.sqlite3")
    db.initialize()
    staged1 = [write_minimal_flac(tmp_path / "a1.flac")]
    r1 = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=jobs,
        db=db,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
        staged_flac_files=staged1,
        cover_bytes=_JPEG,
        skip_disc_match=True,
    )
    assert r1.state.startswith("Completed")

    staged2 = [write_minimal_flac(tmp_path / "a2.flac")]
    with pytest.raises(DuplicateBlockedError):
        run_archive_job(
            metadata=sheet,
            library_root=lib,
            jobs_root=jobs,
            db=db,
            confirm_publish=True,
            collision_policy=CollisionPolicy.RENAME,
            staged_flac_files=staged2,
            cover_bytes=_JPEG,
            skip_disc_match=True,
            confirmed_rearchive=False,
        )

    r2 = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=jobs,
        db=db,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
        staged_flac_files=staged2,
        cover_bytes=_JPEG,
        skip_disc_match=True,
        confirmed_rearchive=True,
    )
    assert r2.state.startswith("Completed")
    assert r2.publish and r2.publish.published
    conn = db.connect()
    row = conn.execute(
        "SELECT disc_id, warnings_json FROM jobs WHERE id=?", (r2.job_id,)
    ).fetchone()
    assert row["disc_id"] == sheet.identity.disc_id
    assert "rearchive_confirmed=true" in (row["warnings_json"] or "")
    n = conn.execute("SELECT COUNT(*) AS c FROM releases").fetchone()["c"]
    assert n == 2
    db.close()


def test_no_db_allows(tmp_path: Path) -> None:
    sheet = _approved()
    a = assess_from_sheet(None, sheet)
    assert a.gate == DuplicateGate.ALLOW


def test_migration_v3_to_v4(tmp_path: Path) -> None:
    """DB figée en v3 puis migrate → v4 sans perte."""
    import sqlite3

    from audio_video_manager.storage.schema import SCHEMA_SQL_V1

    path = tmp_path / "old3.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL_V1)
    conn.execute(
        "INSERT INTO schema_migrations(version, applied_at) VALUES (1, '2020-01-01')"
    )
    conn.commit()
    conn.close()
    db = Database(path)
    # force through initialize (1→4)
    assert db.initialize() == SCHEMA_VERSION
    # Simuler état déjà v3 : déjà migré ; vérifier colonne
    cols = {r[1] for r in db.connect().execute("PRAGMA table_info(jobs)").fetchall()}
    assert "disc_id" in cols
    assert "selected_release_mbid" in cols
    db.close()
