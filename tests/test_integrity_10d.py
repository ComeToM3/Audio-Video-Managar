"""AVM-10D — intégrité catalogue, chemins réservés, espace disque, publish/rollback."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from audio_video_manager.library.disk_space import (
    MARGIN_RATIO,
    check_disk_space,
    estimate_archive_bytes,
    preflight_archive_paths,
)
from audio_video_manager.library.paths import build_library_layout
from audio_video_manager.library.publish import CollisionPolicy, publish_album
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.path_preview import sanitize_segment
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.orchestration.archive_job import run_archive_job
from audio_video_manager.storage import Database
from audio_video_manager.verification.flac_decode import decode_flac_full, require_flac_decode
from audio_video_manager.verification.flac_integrity import check_flac_integrity
from audio_video_manager.verification.rip_check import evaluate_rip_check
from audio_video_manager.verification.track_status import track_verification_status
from tests.flac_fixtures import write_minimal_flac


def _approved(tracks: int = 1):
    sheet = make_approvable_sheet(tracks=tracks)
    sheet.edition.label = "L"
    sheet.edition.catalog_number = "C1"
    sheet.edition.musicbrainz_release_id = "mbid-10d"
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="t")
    return sheet


@pytest.mark.parametrize(
    "raw,expected_prefix",
    [
        ("CON", "_"),
        ("nul", "_"),
        ("PRN", "_"),
        ("COM1", "_"),
        ("LPT9", "_"),
        ("CON.txt", "_"),
        ("Queen", "Q"),
        ("A/B", "A_B"),
    ],
)
def test_sanitize_reserved_windows_names(raw: str, expected_prefix: str) -> None:
    out = sanitize_segment(raw)
    assert out.startswith(expected_prefix) or out[0] == expected_prefix
    if raw.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", "COM1", "LPT9"}:
        assert out.upper() != raw.upper().split(".")[0]
        assert out.startswith("_")


def test_decode_missing_ffmpeg_is_not_success(tmp_path: Path, monkeypatch) -> None:
    flac = write_minimal_flac(tmp_path / "a.flac")
    monkeypatch.delenv("AVM_FFMPEG", raising=False)
    monkeypatch.delenv("AVM_REQUIRE_FLAC_DECODE", raising=False)
    with patch(
        "audio_video_manager.verification.flac_decode.find_flac_decode_tool",
        return_value=None,
    ):
        r = decode_flac_full(flac)
    assert r.attempted is False
    assert r.ok is False  # pas de succès fictif
    assert "non exécuté" in r.message.lower() or "introuvable" in r.message.lower()


def test_track_status_distinguishes_structural_and_decode(tmp_path: Path) -> None:
    flac = write_minimal_flac(tmp_path / "t.flac")
    integ = check_flac_integrity(flac)
    rip = evaluate_rip_check([integ], rip_success=True, cancelled=False)
    with patch(
        "audio_video_manager.verification.flac_decode.find_flac_decode_tool",
        return_value=None,
    ):
        dec = decode_flac_full(flac)
    st = track_verification_status(integ, dec, rip)
    assert st.flac_ok == 1
    assert st.rip_check_status.startswith("weak_ok")
    assert "decode=not_run" in st.rip_check_status


def test_disk_estimate_includes_margin() -> None:
    rawish = estimate_archive_bytes(track_count=10, cross_volume=False)
    assert rawish >= int(10 * 55 * 1024 * 1024 * 2 * MARGIN_RATIO) * 0.99


def test_disk_preflight_fails_when_free_too_low(tmp_path: Path) -> None:
    jobs = tmp_path / "jobs"
    lib = tmp_path / "lib"
    jobs.mkdir()
    lib.mkdir()
    with patch(
        "audio_video_manager.library.disk_space.free_bytes",
        return_value=1024,
    ):
        checks = preflight_archive_paths(
            jobs_dir=jobs, library_root=lib, track_count=5
        )
    assert any(not c.ok for c in checks)


def test_publish_replace_disabled_by_default(tmp_path: Path) -> None:
    sheet = _approved(1)
    layout = build_library_layout(sheet)
    root = tmp_path / "lib"
    album = layout.album_abs(root)
    album.mkdir(parents=True)
    (album / "old.flac").write_bytes(b"x")
    staged = write_minimal_flac(tmp_path / "new.flac")
    res = publish_album(
        library_root=root,
        layout=layout,
        staged_tracks=[staged],
        staged_cover=None,
        policy=CollisionPolicy.REPLACE,
    )
    assert res.published is False
    assert "Replace désactivé" in res.message
    assert (album / "old.flac").is_file()


def test_publish_partial_rollback_keeps_source(tmp_path: Path) -> None:
    sheet = _approved(2)
    layout = build_library_layout(sheet)
    root = tmp_path / "lib"
    s1 = write_minimal_flac(tmp_path / "1.flac")
    s2 = write_minimal_flac(tmp_path / "2.flac")
    calls = {"n": 0}

    def boom(src, dest, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise OSError(28, "No space left on device")
        dest.write_bytes(src.read_bytes())
        return "copy"

    with patch("audio_video_manager.library.transfer.transfer_file", side_effect=boom):
        with pytest.raises(RuntimeError, match="rollback"):
            publish_album(
                library_root=root,
                layout=layout,
                staged_tracks=[s1, s2],
                staged_cover=None,
                policy=CollisionPolicy.RENAME,
            )
    assert s1.is_file() and s2.is_file()
    album = layout.album_abs(root)
    if album.exists():
        # Pas de publication partielle réussie
        flacs = list(album.glob("*.flac"))
        assert flacs == []


def test_archive_records_honest_verification(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_REQUIRE_FLAC_DECODE", raising=False)
    sheet = _approved(1)
    jobs = tmp_path / "jobs"
    lib = tmp_path / "lib"
    jobs.mkdir()
    lib.mkdir()
    db = Database(tmp_path / "a.sqlite3")
    db.initialize()
    flac = write_minimal_flac(tmp_path / "01 - Song.flac")
    with patch(
        "audio_video_manager.verification.flac_decode.find_flac_decode_tool",
        return_value=None,
    ):
        report = run_archive_job(
            metadata=sheet,
            library_root=lib,
            jobs_root=jobs,
            db=db,
            staged_flac_files=[flac],
            skip_disc_match=True,
            confirm_publish=True,
            collision_policy=CollisionPolicy.RENAME,
        )
    assert report.state in {"Completed", "CompletedWithWarnings"}
    assert report.publish and report.publish.published
    row = db.connect().execute(
        "SELECT flac_ok, rip_check_status FROM tracks"
    ).fetchone()
    assert row["flac_ok"] == 1
    assert "weak_ok" in row["rip_check_status"]
    assert "decode=not_run" in row["rip_check_status"]
    assert row["rip_check_status"] != "weak_ok"  # plus de hardcode nu


def test_archive_blocks_when_disk_full(tmp_path: Path) -> None:
    sheet = _approved(1)
    jobs = tmp_path / "jobs"
    lib = tmp_path / "lib"
    jobs.mkdir()
    lib.mkdir()
    db = Database(tmp_path / "b.sqlite3")
    db.initialize()
    flac = write_minimal_flac(tmp_path / "01 - Song.flac")
    with patch(
        "audio_video_manager.library.disk_space.free_bytes",
        return_value=100,
    ):
        report = run_archive_job(
            metadata=sheet,
            library_root=lib,
            jobs_root=jobs,
            db=db,
            staged_flac_files=[flac],
            skip_disc_match=True,
            confirm_publish=True,
        )
    assert report.state == "Failed"
    assert "Espace disque" in (report.error or "")
    # staging source intact
    assert flac.is_file()


def test_archive_blocks_require_decode_without_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AVM_REQUIRE_FLAC_DECODE", "1")
    assert require_flac_decode() is True
    sheet = _approved(1)
    jobs = tmp_path / "jobs"
    lib = tmp_path / "lib"
    jobs.mkdir()
    lib.mkdir()
    db = Database(tmp_path / "c.sqlite3")
    db.initialize()
    flac = write_minimal_flac(tmp_path / "01 - Song.flac")
    with patch(
        "audio_video_manager.verification.flac_decode.find_flac_decode_tool",
        return_value=None,
    ):
        report = run_archive_job(
            metadata=sheet,
            library_root=lib,
            jobs_root=jobs,
            db=db,
            staged_flac_files=[flac],
            skip_disc_match=True,
            confirm_publish=True,
        )
    assert report.state == "Failed"
    assert "ffmpeg" in (report.error or "").lower() or "Décodage" in (report.error or "")
    assert flac.is_file()


def test_corrupted_flac_not_published(tmp_path: Path) -> None:
    sheet = _approved(1)
    jobs = tmp_path / "jobs"
    lib = tmp_path / "lib"
    jobs.mkdir()
    lib.mkdir()
    db = Database(tmp_path / "d.sqlite3")
    db.initialize()
    bad = tmp_path / "01 - Bad.flac"
    bad.write_bytes(b"NOTFLAC" + b"\x00" * 80)
    report = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=jobs,
        db=db,
        staged_flac_files=[bad],
        skip_disc_match=True,
        confirm_publish=True,
    )
    assert report.state == "Failed"
    assert report.failure_kind is not None
    assert db.connect().execute("SELECT COUNT(*) AS n FROM releases").fetchone()["n"] == 0
    assert bad.is_file()
