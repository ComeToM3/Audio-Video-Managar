"""AVM-19 — tests ciblés des corrections de stabilisation du parcours CD.

Couvre : verrou rip exclusif (P1-3), copie TOCTOU-safe (P0-2), rollback
replace (P1-11), collision de noms de pistes (P1-9), nettoyage des tags
FLAC obsolètes (P1-10), délai/429 MusicBrainz (P1-12). L’identification CD
active passe par le wizard et ``IdentifyWorker``; le dialogue indépendant et
ses tests dédiés ont été retirés par AVM-23.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from audio_video_manager.library.paths import build_library_layout
from audio_video_manager.library.publish import CollisionPolicy, publish_album
from audio_video_manager.library.tags import apply_flac_tags, read_flac_tags
from audio_video_manager.library.transfer import transfer_file
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.musicbrainz_client import (
    DEFAULT_TIMEOUT_SEC,
    MAX_RETRY_AFTER_SEC,
    MusicBrainzError,
    lookup_releases_by_discid,
)
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.orchestration.archive_job import run_archive_job
from audio_video_manager.orchestration.rip_lock import (
    RipLockHeldError,
    clear_rip_lock,
    read_rip_lock,
    write_rip_lock,
)
from audio_video_manager.storage import Database
from tests.flac_fixtures import write_minimal_flac


# --- P1-3 : verrou de rip réellement exclusif ---------------------------------


def test_write_rip_lock_raises_when_holder_active(tmp_path: Path) -> None:
    rip = tmp_path / "rip"
    rip.mkdir()
    write_rip_lock(rip, job_id="j1")
    # Le détenteur est notre propre processus (vivant) : un second appel sans
    # libération préalable doit échouer plutôt qu'écraser silencieusement.
    with pytest.raises(RipLockHeldError):
        write_rip_lock(rip, job_id="j2")
    info = read_rip_lock(rip)
    assert info is not None
    assert info.job_id == "j1"


def test_write_rip_lock_reclaims_stale_lock_from_dead_pid(tmp_path: Path) -> None:
    rip = tmp_path / "rip"
    rip.mkdir()
    lock_path = rip / "rip.lock"
    # PID très probablement inutilisé, simulant un verrou abandonné (crash).
    dead_pid = 999_999
    lock_path.write_text(
        json.dumps({"pid": dead_pid, "job_id": "orphan", "started_at": "x", "create_time": None}),
        encoding="utf-8",
    )
    path = write_rip_lock(rip, job_id="fresh")
    info = read_rip_lock(rip)
    assert info is not None
    assert info.job_id == "fresh"
    assert info.pid == os.getpid()
    clear_rip_lock(rip)
    assert not path.exists()


# --- P0-2 : copie de publication TOCTOU-safe -----------------------------------


def test_transfer_copy_refuses_to_overwrite_existing_destination(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AVM_TRANSFER", raising=False)
    src = write_minimal_flac(tmp_path / "a.flac")
    dest = tmp_path / "b.flac"
    dest.write_bytes(b"contenu existant different")

    with pytest.raises(FileExistsError):
        transfer_file(src, dest, mode="copy")

    # Aucune donnée existante n'a été altérée, aucun fichier temporaire ne reste.
    assert dest.read_bytes() == b"contenu existant different"
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".") and "avm-tmp" in p.name]
    assert leftovers == []


# --- P1-11 : rollback sûr de la publication replace ----------------------------


def _approved_sheet(**kwargs):
    sheet = make_approvable_sheet(**kwargs)
    sheet.edition.label = "L"
    sheet.edition.catalog_number = "C1"
    sheet.edition.musicbrainz_release_id = "mbid-rel"
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="t")
    return sheet


def test_publish_replace_rollback_restores_old_album_with_nested_subdir(tmp_path: Path) -> None:
    sheet = _approved_sheet(tracks=2)
    lib = tmp_path / "Music"
    layout = build_library_layout(sheet)

    # Ancien album déjà publié, avec un sous-dossier vide imbriqué (simulant un
    # layout multi-disque) — avant AVM-19, ce résidu empêchait le rollback.
    old_dir = layout.album_abs(lib)
    old_dir.mkdir(parents=True)
    (old_dir / "01 - Old Song.flac").write_bytes(b"old-data-1")
    (old_dir / "02 - Old Song.flac").write_bytes(b"old-data-2")
    (old_dir / "CD1").mkdir()

    src = tmp_path / "src"
    src.mkdir()
    staged = [write_minimal_flac(src / "t1.flac"), write_minimal_flac(src / "t2.flac")]

    # La seconde piste provoque un FileExistsError artificiel pour simuler un
    # échec en cours de publication (ex. cible créée entre-temps par un autre
    # processus) après que l'ancien album a déjà été déplacé vers la corbeille.
    from unittest.mock import patch

    calls = {"n": 0}
    real_transfer_file = transfer_file

    def flaky_transfer(src, dest, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise FileExistsError(f"conflit simulé : {dest}")
        return real_transfer_file(src, dest, **kwargs)

    with patch("audio_video_manager.library.transfer.transfer_file", side_effect=flaky_transfer):
        with pytest.raises(RuntimeError):
            publish_album(
                library_root=lib,
                layout=layout,
                staged_tracks=staged,
                staged_cover=None,
                policy=CollisionPolicy.REPLACE,
                allow_replace=True,
            )

    restored = layout.album_abs(lib)
    assert restored.is_dir()
    assert (restored / "01 - Old Song.flac").read_bytes() == b"old-data-1"
    assert (restored / "02 - Old Song.flac").read_bytes() == b"old-data-2"
    assert (restored / "CD1").is_dir()


# --- P1-9 : collision de noms de pistes après sanitisation ---------------------


def test_archive_job_disambiguates_colliding_track_titles(tmp_path: Path) -> None:
    sheet = _approved_sheet(tracks=2)
    # Titres convergeant vers le même segment sanitisé une fois nettoyés.
    sheet.tracks[0].title = "Même Titre???"
    sheet.tracks[1].title = "Même Titre!!!"
    jobs = tmp_path / "jobs"
    lib = tmp_path / "Music"
    src = tmp_path / "src"
    src.mkdir()
    staged = [write_minimal_flac(src / "t1.flac"), write_minimal_flac(src / "t2.flac")]
    db = Database(tmp_path / "avm.sqlite3")
    db.initialize()

    report = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=jobs,
        db=db,
        confirm_publish=False,
        collision_policy=CollisionPolicy.RENAME,
        staged_flac_files=staged,
        cover_bytes=None,
        skip_disc_match=True,
    )
    db.close()
    assert report.state in (
        "Completed",
        "CompletedWithWarnings",
        "AwaitingPublishConfirmation",
    )
    tagged_dir = report.workdir / "tagged"
    flacs = sorted(p.name for p in tagged_dir.glob("*.flac"))
    assert len(flacs) == 2
    # Les deux fichiers doivent exister distinctement — aucun écrasement.
    assert flacs[0] != flacs[1]


# --- P1-10 : les tags FLAC ne conservent pas de champs obsolètes ---------------


def test_apply_flac_tags_clears_stale_tag_not_in_sheet(tmp_path: Path) -> None:
    sheet = _approved_sheet(tracks=1)
    path = write_minimal_flac(tmp_path / "t.flac")
    from mutagen.flac import FLAC

    audio = FLAC(str(path))
    audio["comment"] = ["un commentaire obsolète fre:ac"]
    audio["genre"] = ["Rock"]
    audio.save()

    apply_flac_tags(path, sheet, sheet.tracks[0])
    tags = read_flac_tags(path)
    assert "comment" not in tags
    assert "genre" not in tags
    assert tags["album"] == sheet.edition.album_title


# --- P1-12 : délais MusicBrainz bornés + 429/Retry-After -----------------------


def test_musicbrainz_lookup_wraps_timeout_error() -> None:
    def boom(*_a, **_k):
        raise TimeoutError("simulated timeout")

    with pytest.raises(MusicBrainzError, match="Délai MusicBrainz"):
        lookup_releases_by_discid("disc123", get_releases_fn=boom)


def test_musicbrainz_429_with_short_retry_after_succeeds_on_retry(monkeypatch) -> None:
    import musicbrainzngs

    calls = {"n": 0}

    class _FakeHeaders:
        def get(self, key):
            return "1" if key == "Retry-After" else None

    class _FakeCause:
        code = 429
        headers = _FakeHeaders()

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            exc = musicbrainzngs.ResponseError("rate limited")
            exc.cause = _FakeCause()
            raise exc
        return {"disc": {"release-list": []}}

    monkeypatch.setattr("time.sleep", lambda _s: None)
    result = lookup_releases_by_discid("disc123", get_releases_fn=flaky)
    assert calls["n"] == 2
    assert result.candidates == []


def test_musicbrainz_429_with_long_retry_after_raises_without_unbounded_wait(monkeypatch) -> None:
    import musicbrainzngs

    class _FakeHeaders:
        def get(self, key):
            return str(MAX_RETRY_AFTER_SEC + 60) if key == "Retry-After" else None

    class _FakeCause:
        code = 429
        headers = _FakeHeaders()

    def always_429(*_a, **_k):
        exc = musicbrainzngs.ResponseError("rate limited")
        exc.cause = _FakeCause()
        raise exc

    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    with pytest.raises(MusicBrainzError, match="429"):
        lookup_releases_by_discid("disc123", get_releases_fn=always_429)
    # Aucune attente de la durée Retry-After (>plafond) n'a été effectuée ;
    # seul le délai de rate-limit normal (<2s) est observé.
    assert all(s < MAX_RETRY_AFTER_SEC for s in sleeps)


def test_default_timeout_is_bounded() -> None:
    assert 0 < DEFAULT_TIMEOUT_SEC <= 60
    assert 0 < MAX_RETRY_AFTER_SEC <= 60
