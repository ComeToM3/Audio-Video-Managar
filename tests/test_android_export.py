from __future__ import annotations

import hashlib
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from audio_video_manager.library import android_export
from audio_video_manager.library.android_export import (
    ANDROID_MUSIC_ROOT,
    scan_android_candidates,
    transfer_android_candidates,
)
from audio_video_manager.storage.android_transfers import list_android_transfers
from audio_video_manager.storage.database import Database


SERIAL = "TEST_ANDROID_01"


class FakeAdb:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.corrupt_push = False
        self.push_count = 0

    def run(self, arguments: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        stdout = ""
        stderr = ""
        returncode = 0
        if arguments[1:3] == ["devices", "-l"]:
            stdout = f"List of devices attached\n{SERIAL} device model:test_phone\n"
        elif "push" in arguments:
            source = Path(arguments[-2])
            destination = arguments[-1]
            data = source.read_bytes()
            self.files[destination] = data + (b"x" if self.corrupt_push else b"")
            self.push_count += 1
            stdout = f"{source}: 1 file pushed"
        elif "shell" in arguments:
            command = arguments[-1]
            parts = shlex.split(command)
            if parts[:2] == ["df", "-k"]:
                stdout = (
                    "Filesystem 1K-blocks Used Available Use% Mounted on\n"
                    "/dev/fuse 1000000 1000 999000 1% /storage/emulated\n"
                )
            elif parts[:2] == ["toybox", "stat"]:
                remote = parts[-1]
                if remote not in self.files:
                    returncode = 1
                    stderr = f"stat: {remote}: No such file or directory"
                else:
                    stdout = f"{len(self.files[remote])}\n"
            elif parts[:2] == ["toybox", "sha256sum"]:
                remote = parts[-1]
                if remote not in self.files:
                    returncode = 1
                    stderr = f"sha256sum: {remote}: No such file or directory"
                else:
                    digest = hashlib.sha256(self.files[remote]).hexdigest()
                    stdout = f"{digest}  {remote}\n"
            elif parts[:2] == ["mkdir", "-p"]:
                pass
            elif parts[:3] == ["toybox", "mv", "-n"]:
                source, destination = parts[-2:]
                if source in self.files and destination not in self.files:
                    self.files[destination] = self.files.pop(source)
            else:
                raise AssertionError(f"Unexpected fake shell command: {command}")
        else:
            raise AssertionError(f"Unexpected fake adb arguments: {arguments}")
        return subprocess.CompletedProcess(arguments, returncode, stdout, stderr)


def _seed(tmp_path: Path) -> tuple[Database, Path, int]:
    root = tmp_path / "library"
    album = root / "Queen" / "Album (2024)"
    album.mkdir(parents=True)
    source = album / "01 - Song.flac"
    source.write_bytes(b"synthetic FLAC payload")
    db = Database(tmp_path / "catalog.sqlite3")
    db.initialize()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    release_id = conn.execute(
        """INSERT INTO releases(album_artist, album, year, path, status, imported_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("Queen", "Album", 2024, str(album), "imported", now),
    ).lastrowid
    track_id = conn.execute(
        "INSERT INTO tracks(release_id, number, title, path, flac_ok) VALUES (?, ?, ?, ?, 1)",
        (release_id, 1, "Song", str(source)),
    ).lastrowid
    conn.commit()
    return db, root, int(track_id)


def test_scan_transfer_and_reconnect_status(tmp_path, monkeypatch) -> None:
    db, root, track_id = _seed(tmp_path)
    fake = FakeAdb()
    monkeypatch.setattr(android_export, "_run", fake.run)
    adb_path = tmp_path / "adb.exe"
    candidates = scan_android_candidates(
        db, adb_path=adb_path, serial=SERIAL, library_root=root
    )
    assert len(candidates) == 1
    assert candidates[0].track_id == track_id
    assert candidates[0].status == "new"
    assert candidates[0].relative_path == "Queen/Album (2024)/01 - Song.flac"

    result = transfer_android_candidates(
        db,
        adb_path=adb_path,
        serial=SERIAL,
        library_root=root,
        candidates=candidates,
    )
    assert (result.succeeded, result.failed, fake.push_count) == (1, 0, 1)
    transfer = list_android_transfers(db, SERIAL)[0]
    assert transfer.status == "succeeded"
    assert transfer.verified_at
    assert transfer.destination_path == (
        f"{ANDROID_MUSIC_ROOT}/Queen/Album (2024)/01 - Song.flac"
    )

    refreshed = scan_android_candidates(
        db, adb_path=adb_path, serial=SERIAL, library_root=root
    )
    assert refreshed[0].status == "transferred"

    old_destination = transfer.destination_path
    old_content = fake.files.pop(old_destination)
    missing = scan_android_candidates(
        db, adb_path=adb_path, serial=SERIAL, library_root=root
    )
    assert missing[0].status == "missing"
    restored = transfer_android_candidates(
        db,
        adb_path=adb_path,
        serial=SERIAL,
        library_root=root,
        candidates=missing,
    )
    assert restored.succeeded == 1
    assert fake.files[old_destination] == old_content

    source = Path(missing[0].source_path)
    source.write_bytes(b"updated synthetic FLAC payload")
    modified = scan_android_candidates(
        db, adb_path=adb_path, serial=SERIAL, library_root=root
    )
    assert modified[0].status == "modified"
    versioned_result = transfer_android_candidates(
        db,
        adb_path=adb_path,
        serial=SERIAL,
        library_root=root,
        candidates=modified,
    )
    assert versioned_result.succeeded == 1
    assert old_destination in fake.files
    assert modified[0].destination_path != old_destination
    assert fake.files[old_destination] == old_content
    db.close()


def test_unknown_destination_is_never_overwritten(tmp_path, monkeypatch) -> None:
    db, root, _track_id = _seed(tmp_path)
    fake = FakeAdb()
    monkeypatch.setattr(android_export, "_run", fake.run)
    destination = f"{ANDROID_MUSIC_ROOT}/Queen/Album (2024)/01 - Song.flac"
    fake.files[destination] = b"unknown phone file"
    candidates = scan_android_candidates(
        db, adb_path=tmp_path / "adb.exe", serial=SERIAL, library_root=root
    )
    assert candidates[0].status == "conflict"

    result = transfer_android_candidates(
        db,
        adb_path=tmp_path / "adb.exe",
        serial=SERIAL,
        library_root=root,
        candidates=candidates,
    )
    assert (result.succeeded, result.failed, result.skipped) == (0, 0, 1)
    assert fake.files[destination] == b"unknown phone file"
    assert fake.push_count == 0
    assert list_android_transfers(db, SERIAL) == []
    db.close()


def test_destination_race_does_not_degrade_previous_success(tmp_path, monkeypatch) -> None:
    db, root, _track_id = _seed(tmp_path)
    fake = FakeAdb()
    monkeypatch.setattr(android_export, "_run", fake.run)
    adb_path = tmp_path / "adb.exe"
    candidate = scan_android_candidates(
        db, adb_path=adb_path, serial=SERIAL, library_root=root
    )[0]
    transfer_android_candidates(
        db,
        adb_path=adb_path,
        serial=SERIAL,
        library_root=root,
        candidates=[candidate],
    )
    destination = list_android_transfers(db, SERIAL)[0].destination_path
    fake.files.pop(destination)
    missing = scan_android_candidates(
        db, adb_path=adb_path, serial=SERIAL, library_root=root
    )
    assert missing[0].status == "missing"

    fake.files[destination] = b"created after scan"
    result = transfer_android_candidates(
        db,
        adb_path=adb_path,
        serial=SERIAL,
        library_root=root,
        candidates=missing,
    )
    transfer = list_android_transfers(db, SERIAL)[0]
    assert result.failed == 1
    assert fake.files[destination] == b"created after scan"
    assert transfer.status == "succeeded"
    assert fake.push_count == 1
    db.close()


def test_failed_verification_keeps_partial_and_failed_history(tmp_path, monkeypatch) -> None:
    db, root, _track_id = _seed(tmp_path)
    fake = FakeAdb()
    fake.corrupt_push = True
    monkeypatch.setattr(android_export, "_run", fake.run)
    adb_path = tmp_path / "adb.exe"
    candidates = scan_android_candidates(
        db, adb_path=adb_path, serial=SERIAL, library_root=root
    )
    result = transfer_android_candidates(
        db,
        adb_path=adb_path,
        serial=SERIAL,
        library_root=root,
        candidates=candidates,
    )
    transfer = list_android_transfers(db, SERIAL)[0]
    assert (result.succeeded, result.failed) == (0, 1)
    assert transfer.status == "failed"
    assert transfer.error_summary
    assert transfer.staging_path in fake.files
    assert transfer.destination_path not in fake.files
    db.close()
