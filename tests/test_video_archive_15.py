from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from audio_video_manager.library.video_archive import finalize_video, index_published_video, reconcile_video, remove_missing_pending_video, reserve_dvd_publication
from audio_video_manager.storage.catalog import list_videos
from audio_video_manager.storage.database import Database


@pytest.fixture
def video_setup(tmp_path, monkeypatch):
    source = tmp_path / "source.mkv"
    source.write_bytes(b"video fixture")
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.touch()
    (tmp_path / "ffprobe.exe").touch()
    db = Database(tmp_path / "catalog.sqlite")
    db.initialize()
    payload = {"format": {"format_name": "matroska,webm", "duration": "10.0"},
               "streams": [{"codec_type": "video", "codec_name": "mpeg2video"}], "chapters": []}

    def fake_run(argv, **kwargs):
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(payload))

    monkeypatch.setattr("audio_video_manager.library.video_archive.subprocess.run", fake_run)
    yield db, source, ffmpeg, tmp_path
    db.close()


def test_finalize_preserves_source_and_indexes_metadata(video_setup):
    db, source, ffmpeg, root = video_setup
    destination = root / "published.mkv"
    video_id = finalize_video(db, source, destination, ffmpeg)
    row = list_videos(db)[0]
    assert row.id == video_id and row.path_exists and row.path_matches
    assert row.validation_status == "decodable" and row.publication_state == "published"
    assert json.loads(row.streams_json)[0]["codec_name"] == "mpeg2video"
    assert destination.read_bytes() == source.read_bytes()
    assert destination.stat().st_ino != source.stat().st_ino
    with pytest.raises(ValueError, match="déjà indexée"):
        finalize_video(db, source, root / "duplicate.mkv", ffmpeg)
    assert not (root / "duplicate.mkv").exists()


def test_existing_destination_and_link_failure_are_not_overwritten(video_setup, monkeypatch):
    db, source, ffmpeg, root = video_setup
    dest = root / "exists.mkv"
    dest.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        finalize_video(db, source, dest, ffmpeg)
    assert dest.read_bytes() == b"existing"
    monkeypatch.setattr("audio_video_manager.library.video_archive.os.link", lambda *_: (_ for _ in ()).throw(OSError("link failed")))
    with pytest.raises(OSError, match="link failed"):
        finalize_video(db, source, root / "not-published.mkv", ffmpeg)
    assert list_videos(db) == []


def test_pending_publication_can_be_reconciled_without_overwriting(video_setup):
    db, source, ffmpeg, root = video_setup
    db.connect().execute("CREATE TRIGGER block_video_update BEFORE UPDATE ON videos BEGIN SELECT RAISE(FAIL, 'test'); END")
    db.connect().commit()
    destination = root / "pending.mkv"
    with pytest.raises(RuntimeError, match="indexation incomplète"):
        finalize_video(db, source, destination, ffmpeg)
    row = list_videos(db)[0]
    assert row.publication_state == "pending" and destination.is_file()
    db.connect().execute("DROP TRIGGER block_video_update")
    db.connect().commit()
    destination.write_bytes(b"changed")
    with pytest.raises(ValueError, match="empreinte"):
        reconcile_video(db, row.id)
    assert list_videos(db)[0].publication_state == "pending"
    destination.write_bytes(source.read_bytes())
    reconcile_video(db, row.id)
    assert list_videos(db)[0].publication_state == "published"


def test_missing_video_is_reported(video_setup):
    db, source, ffmpeg, root = video_setup
    destination = root / "missing.mkv"
    finalize_video(db, source, destination, ffmpeg)
    destination.unlink()
    assert not list_videos(db)[0].path_exists


def test_changed_video_is_reported(video_setup):
    db, source, ffmpeg, root = video_setup
    destination = root / "changed.mkv"
    finalize_video(db, source, destination, ffmpeg)
    destination.write_bytes(b"different content")
    assert list_videos(db)[0].path_exists
    assert not list_videos(db)[0].path_matches


def test_unchanged_content_with_new_timestamp_can_be_reverified(video_setup):
    import os

    db, source, ffmpeg, root = video_setup
    destination = root / "retimed.mkv"
    video_id = finalize_video(db, source, destination, ffmpeg)
    stamp = destination.stat().st_mtime_ns
    os.utime(destination, ns=(stamp + 2_000_000_000, stamp + 2_000_000_000))
    assert not list_videos(db)[0].path_matches
    reconcile_video(db, video_id)
    assert list_videos(db)[0].path_matches


def test_missing_pending_entry_can_be_removed(video_setup):
    db, source, ffmpeg, root = video_setup
    db.connect().execute("CREATE TRIGGER block_video_update BEFORE UPDATE ON videos BEGIN SELECT RAISE(FAIL, 'test'); END")
    db.connect().commit()
    destination = root / "pending.mkv"
    with pytest.raises(RuntimeError):
        finalize_video(db, source, destination, ffmpeg)
    row = list_videos(db)[0]
    with pytest.raises(ValueError, match="fichier existe"):
        remove_missing_pending_video(db, row.id)
    destination.unlink()
    remove_missing_pending_video(db, row.id)
    assert list_videos(db) == []


def test_decode_error_leaves_no_publication(video_setup, monkeypatch):
    db, source, ffmpeg, root = video_setup
    payload = {"format": {"format_name": "matroska", "duration": "10"},
               "streams": [{"codec_type": "video"}], "chapters": []}

    def failing_decode(argv, **kwargs):
        if "-show_format" in argv:
            return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(payload))
        return SimpleNamespace(returncode=1, stderr="corrupt stream", stdout="")

    monkeypatch.setattr("audio_video_manager.library.video_archive.subprocess.run", failing_decode)
    destination = root / "invalid.mkv"
    with pytest.raises(RuntimeError, match="Décodage incomplet"):
        finalize_video(db, source, destination, ffmpeg)
    assert not destination.exists()
    assert list_videos(db) == []
    assert source.read_bytes() == b"video fixture"


def test_index_published_file_without_copy(video_setup):
    db, source, ffmpeg, root = video_setup
    before = source.stat()
    video_id = index_published_video(db, source, ffmpeg)
    row = list_videos(db)[0]
    assert row.id == video_id and row.path == str(source)
    assert row.validation_status == "decodable" and row.publication_state == "published"
    assert source.stat().st_ino == before.st_ino
    assert source.read_bytes() == b"video fixture"
    with pytest.raises(ValueError, match="déjà indexée"):
        index_published_video(db, source, ffmpeg)


def test_index_published_audio_only(video_setup, monkeypatch):
    db, source, ffmpeg, root = video_setup
    audio = root / "audio.mka"
    audio.write_bytes(b"audio fixture")
    payload = {"format": {"format_name": "matroska,webm", "duration": "10"},
               "streams": [{"codec_type": "audio", "codec_name": "ac3"}], "chapters": []}
    monkeypatch.setattr("audio_video_manager.library.video_archive.subprocess.run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""))
    index_published_video(db, audio, ffmpeg)
    assert list_videos(db)[0].path == str(audio)


def test_cancel_index_preserves_published_file(video_setup):
    import threading

    db, source, ffmpeg, root = video_setup
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(InterruptedError):
        index_published_video(db, source, ffmpeg, cancel_event=cancel)
    assert source.read_bytes() == b"video fixture"
    assert list_videos(db) == []


def test_dvd_reservation_survives_until_validated(video_setup):
    db, source, ffmpeg, root = video_setup
    destination = root / "dvd.mkv"
    reservation = reserve_dvd_publication(db, destination)
    row = list_videos(db)[0]
    assert row.id == reservation and row.validation_status == "incomplete"
    assert row.publication_state == "pending" and not row.path_exists
    with pytest.raises(ValueError, match="déjà indexée"):
        reserve_dvd_publication(db, destination)
    destination.write_bytes(source.read_bytes())
    assert index_published_video(db, destination, ffmpeg, reservation_id=reservation) == reservation
    row = list_videos(db)[0]
    assert row.validation_status == "decodable" and row.publication_state == "published"
    assert row.path_matches


def test_failed_dvd_index_retains_reservation_and_file(video_setup, monkeypatch):
    db, source, ffmpeg, root = video_setup
    destination = root / "dvd.mkv"
    reservation = reserve_dvd_publication(db, destination)
    destination.write_bytes(source.read_bytes())
    monkeypatch.setattr("audio_video_manager.library.video_archive._inspect_decodable", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("validation failed")))
    with pytest.raises(RuntimeError, match="validation failed"):
        index_published_video(db, destination, ffmpeg, reservation_id=reservation)
    assert destination.read_bytes() == source.read_bytes()
    row = list_videos(db)[0]
    assert row.publication_state == "pending" and row.validation_status == "incomplete"


def test_cancel_during_decode_keeps_reservation_and_file(video_setup):
    db, source, ffmpeg, root = video_setup
    destination = root / "dvd.mkv"
    reservation = reserve_dvd_publication(db, destination)
    destination.write_bytes(source.read_bytes())

    def cancelled(_argv, _duration):
        raise InterruptedError("annulée")

    with pytest.raises(InterruptedError, match="annulée"):
        index_published_video(db, destination, ffmpeg, reservation_id=reservation, decode_runner=cancelled)
    assert destination.read_bytes() == source.read_bytes()
    assert list_videos(db)[0].publication_state == "pending"


def test_duplicate_dvd_content_preserves_both_files_and_pending_entry(video_setup):
    db, source, ffmpeg, root = video_setup
    index_published_video(db, source, ffmpeg)
    destination = root / "duplicate-dvd.mkv"
    reservation = reserve_dvd_publication(db, destination)
    destination.write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="déjà indexée"):
        index_published_video(db, destination, ffmpeg, reservation_id=reservation)
    assert destination.read_bytes() == source.read_bytes()
    assert sorted(row.publication_state for row in list_videos(db)) == ["pending", "published"]