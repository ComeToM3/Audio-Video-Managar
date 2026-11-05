"""AVM-06G-P1 — sécurité hardlinks, isolation mutations, rollback, disc swap."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from audio_video_manager.library.disc_match import DiscMismatchError
from audio_video_manager.library.paths import build_library_layout
from audio_video_manager.library.publish import CollisionPolicy, publish_album
from audio_video_manager.library.tags import apply_flac_tags, read_flac_tags
from audio_video_manager.library.transfer import (
    ensure_exclusive_file,
    link_count,
    same_file,
    transfer_file,
)
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.toc_reader import DiscReadResult
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.orchestration.archive_job import run_archive_job
from audio_video_manager.storage import Database
from tests.flac_fixtures import write_minimal_flac


def _approved(tracks: int = 1):
    sheet = make_approvable_sheet(tracks=tracks)
    sheet.edition.label = "L"
    sheet.edition.catalog_number = "C1"
    sheet.edition.musicbrainz_release_id = "mbid-rel"
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="t")
    return sheet


def test_hardlink_same_inode_and_unlink_one_keeps_other(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    src = write_minimal_flac(tmp_path / "a.flac")
    payload = src.read_bytes()
    dest = tmp_path / "b.flac"
    assert transfer_file(src, dest, mode="link") == "hardlink"
    assert same_file(src, dest)
    assert link_count(src) >= 2
    dest.unlink()
    assert src.is_file()
    assert src.read_bytes() == payload
    assert link_count(src) == 1


def test_transfer_falls_back_to_copy_when_os_link_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    src = write_minimal_flac(tmp_path / "a.flac")
    dest = tmp_path / "b.flac"

    def boom(*_a, **_k):
        raise OSError(17, "simulated cross-volume")

    with patch("audio_video_manager.library.transfer.os.link", side_effect=boom):
        assert transfer_file(src, dest, mode="auto") == "copy"
    assert dest.is_file()
    assert not same_file(src, dest)
    assert src.read_bytes() == dest.read_bytes()


def test_transfer_link_mode_raises_without_fallback(tmp_path: Path) -> None:
    src = write_minimal_flac(tmp_path / "a.flac")
    dest = tmp_path / "b.flac"

    with patch(
        "audio_video_manager.library.transfer.os.link",
        side_effect=OSError(17, "fail"),
    ):
        with pytest.raises(OSError):
            transfer_file(src, dest, mode="link")


def test_ensure_exclusive_breaks_hardlink_before_mutation(tmp_path: Path) -> None:
    src = write_minimal_flac(tmp_path / "shared.flac")
    link = tmp_path / "alias.flac"
    os.link(src, link)
    assert same_file(src, link)
    assert ensure_exclusive_file(link) is True
    assert not same_file(src, link)
    # muter l’alias ne doit plus toucher la source
    link.write_bytes(b"MUTATED-NOT-FLAC")
    assert src.read_bytes() != link.read_bytes()


def test_apply_flac_tags_isolates_hardlinked_source(tmp_path: Path) -> None:
    sheet = _approved(1)
    original = write_minimal_flac(tmp_path / "orig.flac")
    before = original.read_bytes()
    linked = tmp_path / "linked.flac"
    os.link(original, linked)
    apply_flac_tags(linked, sheet, sheet.tracks[0])
    tags = read_flac_tags(linked)
    assert tags["title"] == sheet.tracks[0].title
    # l’original (autre nom du même inode AVANT isolation) reste non tagué
    assert not same_file(original, linked)
    assert original.read_bytes() == before


def test_publish_c_is_independent_copy_not_hardlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    sheet = _approved(1)
    layout = build_library_layout(sheet)
    staged = write_minimal_flac(tmp_path / "01.flac")
    r = publish_album(
        library_root=tmp_path / "Music",
        layout=layout,
        staged_tracks=[staged],
        staged_cover=None,
        policy=CollisionPolicy.RENAME,
    )
    assert r.published and r.track_paths
    published = r.track_paths[0]
    assert published.is_file()
    assert not same_file(staged, published)
    assert "copy" in r.message
    # muter staging ne touche pas C
    staged.write_bytes(b"X" * 64)
    assert published.read_bytes() != staged.read_bytes()


def test_publish_rollback_unlinks_dest_keeps_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AVM_TRANSFER", "auto")
    sheet = _approved(2)
    layout = build_library_layout(sheet)
    s1 = write_minimal_flac(tmp_path / "01.flac")
    s2 = write_minimal_flac(tmp_path / "02.flac")
    before1, before2 = s1.read_bytes(), s2.read_bytes()
    lib = tmp_path / "Music"

    real_transfer = transfer_file
    calls = {"n": 0}

    def flaky(src, dest, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            # Premier fichier OK, second échoue après création partielle simulée
            raise OSError("simulated mid-publish failure")
        return real_transfer(src, dest, **kwargs)

    with patch(
        "audio_video_manager.library.transfer.transfer_file",
        side_effect=flaky,
    ):
        with pytest.raises(RuntimeError, match="rollback"):
            publish_album(
                library_root=lib,
                layout=layout,
                staged_tracks=[s1, s2],
                staged_cover=None,
                policy=CollisionPolicy.RENAME,
            )

    assert s1.read_bytes() == before1
    assert s2.read_bytes() == before2
    # Pas de FLAC orphelin publié (rollback a unlink les écrits)
    leftover = list(lib.rglob("*.flac")) if lib.exists() else []
    assert leftover == []


def test_inbox_may_hardlink_tagged_but_c_independent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    sheet = _approved(1)
    src = tmp_path / "src"
    src.mkdir()
    staged = [write_minimal_flac(src / "01.flac")]
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    report = run_archive_job(
        metadata=sheet,
        library_root=tmp_path / "Music",
        jobs_root=tmp_path / "jobs",
        db=db,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
        staged_flac_files=staged,
        skip_disc_match=True,
    )
    assert report.state.startswith("Completed")
    assert report.inbox_dir and report.publish and report.publish.album_dir
    tagged = next((report.workdir / "tagged").glob("*.flac"))
    inbox = next(report.inbox_dir.glob("*.flac"))
    published = report.publish.track_paths[0]
    # inbox peut partager tagged
    assert same_file(tagged, inbox) or link_count(tagged) >= 1
    # C est indépendant
    assert not same_file(tagged, published)
    assert not same_file(inbox, published)


def test_disc_swap_detected_via_fresh_toc_vs_sheet(tmp_path: Path) -> None:
    """CD remplacé : la relecture ne correspond plus à la fiche Approved."""
    sheet = _approved(1)
    toc = sheet.identity.toc
    assert toc is not None
    stale = DiscReadResult(
        disc_id=sheet.identity.disc_id or "old",
        toc=toc,
        device="D:",
    )
    fresh = DiscReadResult(disc_id="REPLACED-DISC-ID", toc=toc, device="D:")

    with patch(
        "audio_video_manager.orchestration.archive_job.read_disc_toc",
        return_value=fresh,
    ):
        with pytest.raises(DiscMismatchError, match="fiche|lecteur|Disc ID"):
            run_archive_job(
                metadata=sheet,
                library_root=tmp_path / "M",
                jobs_root=tmp_path / "j",
                freaccmd=tmp_path / "fake-freaccmd.exe",
                disc_read=stale,
                staged_flac_files=None,
                confirm_publish=False,
                skip_disc_match=False,
            )


def test_stale_identify_read_vs_fresh_same_sheet_detected(tmp_path: Path) -> None:
    """disc_read d’identify désynchronisé alors que le lecteur actuel = fiche."""
    sheet = _approved(1)
    toc = sheet.identity.toc
    assert toc is not None
    fresh = DiscReadResult(
        disc_id=sheet.identity.disc_id or "",
        toc=toc,
        device="D:",
    )
    stale = DiscReadResult(disc_id="OLD-IDENTIFY-ID", toc=toc, device="D:")

    with patch(
        "audio_video_manager.orchestration.archive_job.read_disc_toc",
        return_value=fresh,
    ):
        with pytest.raises(DiscMismatchError, match="changé depuis"):
            run_archive_job(
                metadata=sheet,
                library_root=tmp_path / "M",
                jobs_root=tmp_path / "j",
                freaccmd=tmp_path / "fake-freaccmd.exe",
                disc_read=stale,
                staged_flac_files=None,
                confirm_publish=False,
            )


def test_stale_matching_disc_read_still_requires_fresh_toc(tmp_path: Path) -> None:
    """Même si disc_read == fiche, un rip réel doit relire le lecteur."""
    sheet = _approved(1)
    toc = sheet.identity.toc
    assert toc is not None
    good = DiscReadResult(
        disc_id=sheet.identity.disc_id or "",
        toc=toc,
        device="D:",
    )
    called: list[bool] = []

    def fake_read(_device=None):
        called.append(True)
        return good

    with patch(
        "audio_video_manager.orchestration.archive_job.read_disc_toc",
        side_effect=fake_read,
    ):
        with patch(
            "audio_video_manager.orchestration.archive_job.FreacCdRipper"
        ) as rip_cls:
            # Arrêter après disc match : ripper lève pour éviter vrai fre:ac
            rip_cls.side_effect = RuntimeError("stop-after-match")
            with pytest.raises(RuntimeError, match="stop-after-match"):
                run_archive_job(
                    metadata=sheet,
                    library_root=tmp_path / "M",
                    jobs_root=tmp_path / "j",
                    freaccmd=tmp_path / "freaccmd.exe",
                    disc_read=good,
                    staged_flac_files=None,
                    confirm_publish=False,
                )
    assert called == [True]


def test_independent_flag_ignores_auto_hardlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AVM_TRANSFER", "auto")
    src = write_minimal_flac(tmp_path / "a.flac")
    dest = tmp_path / "b.flac"
    assert transfer_file(src, dest, independent=True) == "copy"
    assert not same_file(src, dest)
