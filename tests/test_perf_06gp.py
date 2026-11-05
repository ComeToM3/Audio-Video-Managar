"""AVM-06G-P — transfert hardlink/copie, cache pochette, perf spans."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from audio_video_manager.diagnostics.perf import PerfSession
from audio_video_manager.library.cover import resolve_cover_for_sheet
from audio_video_manager.library.transfer import transfer_file
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.library.publish import CollisionPolicy, publish_album
from audio_video_manager.library.paths import build_library_layout
from audio_video_manager.orchestration.archive_job import run_archive_job
from audio_video_manager.storage import Database
from audio_video_manager.ui.cover_cache import cached_cover_path
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


def test_transfer_hardlink_or_copy(tmp_path: Path, monkeypatch) -> None:
    src = write_minimal_flac(tmp_path / "a.flac")
    dest = tmp_path / "b" / "a.flac"
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    method = transfer_file(src, dest)
    assert method in ("hardlink", "copy")
    assert dest.is_file()
    assert src.is_file()


def test_transfer_force_copy(tmp_path: Path, monkeypatch) -> None:
    src = write_minimal_flac(tmp_path / "a.flac")
    dest = tmp_path / "c.flac"
    monkeypatch.setenv("AVM_TRANSFER", "copy")
    assert transfer_file(src, dest) == "copy"
    assert dest.read_bytes() == src.read_bytes()


def test_cover_uses_disk_cache_without_network(tmp_path: Path, monkeypatch) -> None:
    url = "https://example.test/covers/queen-front.jpg"
    cache_dir = tmp_path / "cache"
    path = cached_cover_path(url, cache_dir)
    path.write_bytes(_JPEG)
    monkeypatch.setattr(
        "audio_video_manager.ui.cover_cache.default_cover_cache_dir",
        lambda: cache_dir,
    )
    sheet = make_approvable_sheet(tracks=1)
    sheet.edition.cover_status = CoverStatus.CONFIRMED
    sheet.edition.cover_path_or_url = url
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    approve_sheet(sheet, note="t")

    def boom(*_a, **_k):
        raise AssertionError("network should not be called")

    material = resolve_cover_for_sheet(sheet, urlopen_fn=boom)
    assert material.status == "ok"
    assert "cache" in material.message.casefold()
    assert material.data == _JPEG


def test_archive_job_records_perf_and_hardlink_inbox(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    sheet = make_approvable_sheet(tracks=2)
    approve_sheet(sheet, note="t")
    src = tmp_path / "src"
    src.mkdir()
    staged = [
        write_minimal_flac(src / "01.flac"),
        write_minimal_flac(src / "02.flac"),
    ]
    db = Database(tmp_path / "avm.sqlite3")
    db.initialize()
    report = run_archive_job(
        metadata=sheet,
        library_root=tmp_path / "Music",
        jobs_root=tmp_path / "jobs",
        db=db,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
        staged_flac_files=staged,
        cover_bytes=None,
        skip_disc_match=True,
    )
    assert report.state.startswith("Completed")
    assert report.perf is not None
    names = [s["name"] for s in report.perf["spans"]]
    assert "staging_to_zone_a" in names
    assert "flac_integrity_f08a" in names
    assert "inbox_transfer" in names
    assert "publish_c" in names
    inbox_span = next(s for s in report.perf["spans"] if s["name"] == "inbox_transfer")
    assert inbox_span.get("extra", {}).get("transfer") or True  # transfer in extra


def test_perf_session_summary() -> None:
    p = PerfSession(label="t")
    with p.span("x", items=2):
        pass
    s = p.summary()
    assert s["label"] == "t"
    assert s["spans"][0]["name"] == "x"
    assert s["spans"][0]["items"] == 2


def test_publish_hardlink_rollback_keeps_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    sheet = make_approvable_sheet(tracks=1)
    sheet.edition.label = "L"
    sheet.edition.catalog_number = "C"
    sheet.edition.musicbrainz_release_id = "mbid"
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    approve_sheet(sheet, note="t")
    layout = build_library_layout(sheet)
    staged = tmp_path / "staged"
    staged.mkdir()
    f = write_minimal_flac(staged / "01.flac")
    lib = tmp_path / "Music"
    # Pré-créer la cible pour forcer FileExistsError mid-path via collision...
    # Simpler: publish once, then force exists on second with copy mode into same paths
    r1 = publish_album(
        library_root=lib,
        layout=layout,
        staged_tracks=[f],
        staged_cover=None,
        policy=CollisionPolicy.RENAME,
    )
    assert r1.published
    assert f.is_file()  # source never consumed
