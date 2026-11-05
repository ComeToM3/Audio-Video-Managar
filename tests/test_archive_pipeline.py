"""AVM-05 — pipeline archive (staging injecté, pas de rip réel)."""

from __future__ import annotations

from pathlib import Path

import pytest

from audio_video_manager.library.cover import validate_image_bytes
from audio_video_manager.library.disc_match import (
    DiscMismatchError,
    assert_disc_matches_sheet,
    verify_disc_matches_sheet,
)
from audio_video_manager.library.paths import build_library_layout
from audio_video_manager.library.publish import CollisionPolicy, publish_album
from audio_video_manager.library.tags import apply_flac_tags, read_flac_tags
from audio_video_manager.metadata.enums import ApprovalState, CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta, TocSnapshot
from audio_video_manager.metadata.toc_reader import DiscReadResult
from audio_video_manager.metadata.validation import approve_sheet, assert_can_start_archive_rip
from audio_video_manager.orchestration.archive_job import (
    match_flacs_to_tracks,
    run_archive_job,
)
from audio_video_manager.storage import Database
from tests.flac_fixtures import write_minimal_flac

# Minimal JPEG (1x1)
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


def _approved_sheet(**kwargs):
    sheet = make_approvable_sheet(**kwargs)
    sheet.edition.label = "Test Label"
    sheet.edition.catalog_number = "CAT-1"
    sheet.edition.musicbrainz_release_id = "mbid-release-test"
    sheet.edition.cover_status = CoverStatus.CONFIRMED
    sheet.edition.cover_path_or_url = "https://example.test/cover.jpg"
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    approve_sheet(sheet, note="test")
    return sheet


def test_validate_jpeg_magic() -> None:
    ok, mime = validate_image_bytes(_JPEG)
    assert ok and mime == "image/jpeg"


def test_tags_roundtrip(tmp_path: Path) -> None:
    sheet = _approved_sheet()
    flac = write_minimal_flac(tmp_path / "01.flac")
    tags = apply_flac_tags(
        flac, sheet, sheet.tracks[0], cover_image=_JPEG, cover_mime="image/jpeg"
    )
    assert tags["title"] == "Song 1"
    assert tags["album"] == "Demo Album"
    assert tags["albumartist"] == "Demo Artist"
    assert tags["musicbrainz_albumid"] == "mbid-release-test"
    assert tags["_pictures"] == 1
    again = read_flac_tags(flac)
    assert again["tracknumber"] == "01"


def test_disc_match_ok_and_mismatch() -> None:
    sheet = _approved_sheet()
    toc = sheet.identity.toc
    assert toc is not None
    good = DiscReadResult(
        disc_id=sheet.identity.disc_id or "",
        toc=toc,
        device="D:",
    )
    assert verify_disc_matches_sheet(sheet, good).ok
    bad = DiscReadResult(
        disc_id="other.id",
        toc=toc,
        device="D:",
    )
    with pytest.raises(DiscMismatchError):
        assert_disc_matches_sheet(sheet, bad)


def test_match_flacs_incomplete() -> None:
    with pytest.raises(Exception):
        match_flacs_to_tracks([Path("a.flac")], 2)


def test_publish_skip_rename_replace(tmp_path: Path) -> None:
    sheet = _approved_sheet()
    layout = build_library_layout(sheet)
    lib = tmp_path / "Music"
    # prepare staged
    staged = tmp_path / "staged"
    staged.mkdir()
    files = []
    for i, rel in enumerate(layout.track_rels):
        p = write_minimal_flac(staged / f"{i+1:02d}.flac")
        files.append(p)
    cover = staged / "cover.jpg"
    cover.write_bytes(_JPEG)

    r1 = publish_album(
        library_root=lib,
        layout=layout,
        staged_tracks=files,
        staged_cover=cover,
        policy=CollisionPolicy.RENAME,
    )
    assert r1.published and r1.album_dir and r1.album_dir.is_dir()
    assert (r1.album_dir / "cover.jpg").is_file()

    # collision skip
    r_skip = publish_album(
        library_root=lib,
        layout=layout,
        staged_tracks=files,
        staged_cover=cover,
        policy=CollisionPolicy.SKIP,
    )
    assert r_skip.skipped and not r_skip.published

    # rename
    r_ren = publish_album(
        library_root=lib,
        layout=layout,
        staged_tracks=files,
        staged_cover=cover,
        policy=CollisionPolicy.RENAME,
    )
    assert r_ren.published
    assert "import-2" in str(r_ren.album_dir)

    # replace moves old to trash — seulement avec allow_replace explicite (AVM-10D)
    r_blocked = publish_album(
        library_root=lib,
        layout=layout,
        staged_tracks=files,
        staged_cover=cover,
        policy=CollisionPolicy.REPLACE,
    )
    assert not r_blocked.published
    assert "Replace désactivé" in r_blocked.message

    r_rep = publish_album(
        library_root=lib,
        layout=layout,
        staged_tracks=files,
        staged_cover=cover,
        policy=CollisionPolicy.REPLACE,
        allow_replace=True,
    )
    assert r_rep.published
    assert r_rep.trash_dir is not None and r_rep.trash_dir.exists()


def test_publish_incomplete_refused(tmp_path: Path) -> None:
    sheet = _approved_sheet(tracks=2)
    layout = build_library_layout(sheet)
    staged = [write_minimal_flac(tmp_path / "01.flac")]
    r = publish_album(
        library_root=tmp_path / "Music",
        layout=layout,
        staged_tracks=staged,
        staged_cover=None,
        policy=CollisionPolicy.RENAME,
    )
    assert not r.published
    assert "incomplet" in r.message.lower()


def test_archive_pipeline_publish(tmp_path: Path) -> None:
    sheet = _approved_sheet(tracks=2)
    jobs = tmp_path / "jobs"
    lib = tmp_path / "Music"
    src = tmp_path / "src"
    src.mkdir()
    staged = [
        write_minimal_flac(src / "track01.flac"),
        write_minimal_flac(src / "track02.flac"),
    ]
    db = Database(tmp_path / "avm.sqlite3")
    db.initialize()

    report = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=jobs,
        db=db,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
        staged_flac_files=staged,
        cover_bytes=_JPEG,
        skip_disc_match=True,
    )
    assert report.state in ("Completed", "CompletedWithWarnings")
    assert report.publish and report.publish.published
    assert report.inbox_dir and report.inbox_dir.is_dir()
    album = report.publish.album_dir
    assert album is not None
    flacs = list(album.glob("*.flac"))
    assert len(flacs) == 2
    tags = read_flac_tags(flacs[0])
    assert tags["album"] == "Demo Album"
    assert tags["_pictures"] == 1
    # gate still required for rip — already approved
    assert_can_start_archive_rip(sheet)
    conn = db.connect()
    row = conn.execute("SELECT state, selected_release_mbid FROM jobs WHERE id=?", (report.job_id,)).fetchone()
    assert row["state"].startswith("Completed")
    assert row["selected_release_mbid"] == "mbid-release-test"
    rel = conn.execute("SELECT album FROM releases").fetchone()
    assert rel["album"] == "Demo Album"
    db.close()


def test_archive_without_publish_stays_inbox(tmp_path: Path) -> None:
    sheet = _approved_sheet(tracks=1)
    staged = [write_minimal_flac(tmp_path / "t1.flac")]
    report = run_archive_job(
        metadata=sheet,
        library_root=tmp_path / "Music",
        jobs_root=tmp_path / "jobs",
        confirm_publish=False,
        staged_flac_files=staged,
        cover_bytes=_JPEG,
        skip_disc_match=True,
    )
    assert report.state == "AwaitingPublishConfirmation"
    assert report.publish is None
    assert report.inbox_dir and any(report.inbox_dir.glob("*.flac"))
    # C must be empty of album
    music = tmp_path / "Music"
    artists = [p for p in music.iterdir() if p.name != "_inbox"] if music.exists() else []
    assert artists == [] or all(p.name.startswith(".") for p in artists)


def test_archive_rejects_unapproved(tmp_path: Path) -> None:
    sheet = make_approvable_sheet()
    assert sheet.approval == ApprovalState.PENDING
    with pytest.raises(Exception):
        run_archive_job(
            metadata=sheet,
            library_root=tmp_path / "M",
            jobs_root=tmp_path / "j",
            staged_flac_files=[write_minimal_flac(tmp_path / "a.flac")],
            skip_disc_match=True,
            confirm_publish=True,
        )


def test_disc_match_blocks_archive(tmp_path: Path) -> None:
    sheet = _approved_sheet(tracks=1)
    toc = sheet.identity.toc
    assert toc is not None
    bad = DiscReadResult(disc_id="WRONG", toc=toc, device="D:")
    with pytest.raises(DiscMismatchError):
        run_archive_job(
            metadata=sheet,
            library_root=tmp_path / "M",
            jobs_root=tmp_path / "j",
            staged_flac_files=[write_minimal_flac(tmp_path / "a.flac")],
            disc_read=bad,
            confirm_publish=False,
        )
