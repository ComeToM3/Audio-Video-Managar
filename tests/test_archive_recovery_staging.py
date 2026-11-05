"""AVM-06F — reprise staging : pas de rip, nouveau job, originaux préservés, Failed intact."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from audio_video_manager.extraction.cd_ripper import FreacCdRipper, build_freaccmd_rip_argv, RipRequest
from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.library.tags import read_flac_tags
from audio_video_manager.metadata.enums import ApprovalState, CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet, assert_can_start_archive_rip
from audio_video_manager.orchestration.archive_job import run_archive_job
from audio_video_manager.storage import Database
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


def _approved(tracks: int = 2):
    sheet = make_approvable_sheet(tracks=tracks)
    sheet.edition.label = "Hollywood"
    sheet.edition.catalog_number = "CD 61265"
    sheet.edition.musicbrainz_release_id = "4662a6ff-34e5-462f-bac0-584ac29cfd4d"
    sheet.edition.cover_status = CoverStatus.CONFIRMED
    sheet.edition.cover_path_or_url = "https://example.test/cover.jpg"
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    approve_sheet(sheet, note="06F")
    return sheet


def test_pattern_equals_still_required_strict_returncode() -> None:
    """06E + politique stricte : argv pattern= ; success exige returncode 0."""
    exe = Path("freaccmd.exe")
    argv = build_freaccmd_rip_argv(
        RipRequest(freaccmd=exe, drive_number=0, workdir=Path("out"), pattern="<track>")
    )
    assert "--pattern=<track>" in argv
    assert "<track>" not in argv


def test_staged_recovery_never_calls_freac_rip(tmp_path: Path) -> None:
    sheet = _approved(2)
    src = tmp_path / "failed_job_rip"
    src.mkdir()
    originals = [
        write_minimal_flac(src / "1.flac"),
        write_minimal_flac(src / "2.flac"),
    ]
    before = [p.read_bytes() for p in originals]
    mtimes = [p.stat().st_mtime for p in originals]

    lib = tmp_path / "AVM-06C-Test-Library"
    jobs = tmp_path / "jobs"
    db = Database(tmp_path / "avm.sqlite3")
    db.initialize()

    # Job Failed préexistant (ne doit pas passer à Completed)
    failed_id = "bd40b604b7a147b985916f9f97f70223"
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, metadata_id, publish_allowed, collision_policy, warnings_json)
        VALUES (?, 'Failed', 'Failed', ?, 't0', 't1', 't1',
            'freaccmd returncode=4294967293', 'normal', ?, 1, 'rename', '[]')
        """,
        (failed_id, str(src.parent), sheet.id),
    )
    conn.commit()

    with patch.object(FreacCdRipper, "rip", autospec=True) as rip_mock:
        report = run_archive_job(
            metadata=sheet,
            library_root=lib,
            jobs_root=jobs,
            db=db,
            freaccmd=tmp_path / "should-not-run.exe",
            confirm_publish=True,
            collision_policy=CollisionPolicy.RENAME,
            staged_flac_files=originals,
            cover_bytes=_JPEG,
            skip_disc_match=True,
        )
        rip_mock.assert_not_called()

    assert report.rip is not None
    assert report.rip.argv == ("staged",)
    assert report.rip.returncode == 0
    assert report.state.startswith("Completed")
    assert report.publish and report.publish.published
    assert report.job_id != failed_id

    # Originaux intacts (copie, pas move)
    for p, data, mt in zip(originals, before, mtimes):
        assert p.is_file()
        assert p.read_bytes() == data
        assert p.stat().st_mtime == mt

    # Nouveau workdir distinct
    assert failed_id not in str(report.workdir)
    assert (report.workdir / "rip").is_dir()

    conn = db.connect()
    failed = conn.execute("SELECT state, error_summary FROM jobs WHERE id=?", (failed_id,)).fetchone()
    assert failed["state"] == "Failed"
    assert "4294967293" in failed["error_summary"]
    new = conn.execute("SELECT state FROM jobs WHERE id=?", (report.job_id,)).fetchone()
    assert new["state"].startswith("Completed")

    album = report.publish.album_dir
    assert album is not None
    assert lib in album.parents or album.is_relative_to(lib)
    assert len(list(album.glob("*.flac"))) == 2
    assert (album / "cover.jpg").is_file()
    tags = read_flac_tags(next(album.glob("*.flac")))
    assert tags["album"] == "Demo Album"
    db.close()


def test_staged_requires_approval(tmp_path: Path) -> None:
    sheet = make_approvable_sheet(tracks=1)
    assert sheet.approval == ApprovalState.PENDING
    with pytest.raises(Exception):
        assert_can_start_archive_rip(sheet)
    with pytest.raises(Exception):
        run_archive_job(
            metadata=sheet,
            library_root=tmp_path / "lib",
            jobs_root=tmp_path / "jobs",
            staged_flac_files=[write_minimal_flac(tmp_path / "1.flac")],
            skip_disc_match=True,
            confirm_publish=True,
        )


def test_staged_rename_not_replace_default(tmp_path: Path) -> None:
    sheet = _approved(1)
    lib = tmp_path / "AVM-06C-Test-Library"
    # pré-créer collision
    first = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=tmp_path / "jobs1",
        staged_flac_files=[write_minimal_flac(tmp_path / "a1.flac")],
        cover_bytes=_JPEG,
        skip_disc_match=True,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
    )
    assert first.publish and first.publish.published
    second = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=tmp_path / "jobs2",
        staged_flac_files=[write_minimal_flac(tmp_path / "a2.flac")],
        cover_bytes=_JPEG,
        skip_disc_match=True,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
    )
    assert second.publish and second.publish.published
    assert first.publish.album_dir != second.publish.album_dir
    assert first.publish.album_dir and first.publish.album_dir.is_dir()
