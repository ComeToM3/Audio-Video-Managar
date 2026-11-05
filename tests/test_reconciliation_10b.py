"""AVM-10B — réconciliation jobs / récupération staging contrôlée (déterministe)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.repository import DiscMetadataRepository
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.orchestration.reconciliation import (
    LivenessKind,
    RecoveryVerdict,
    assess_recovery_from_files,
    list_job_flac_files,
    list_unfinished_active_jobs,
    mark_job_abandoned,
    mark_job_interrupted,
    reconcile_unfinished_jobs,
    recovery_in_progress,
    release_recovery,
    run_recovery_from_files,
    try_acquire_recovery,
    write_rip_lock,
    clear_rip_lock,
    read_rip_lock,
)
from audio_video_manager.orchestration.rip_lock import LOCK_FILENAME
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


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _approved(tracks: int = 2):
    sheet = make_approvable_sheet(tracks=tracks)
    sheet.edition.label = "Hollywood"
    sheet.edition.catalog_number = "CD 61265"
    sheet.edition.musicbrainz_release_id = "4662a6ff-34e5-462f-bac0-584ac29cfd4d"
    sheet.edition.cover_status = CoverStatus.CONFIRMED
    sheet.edition.cover_path_or_url = "https://example.test/cover.jpg"
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    approve_sheet(sheet, note="10B")
    return sheet


def _seed_active_rip(
    db: Database,
    *,
    jid: str,
    workdir: Path,
    mode: str = "technical_test",
    metadata_id: str | None = None,
    state: str = "Ripping",
) -> None:
    now = _now()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, metadata_id, publish_allowed, disc_id
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, 0, ?)
        """,
        (
            jid,
            state,
            state,
            str(workdir),
            now,
            now,
            mode,
            metadata_id,
            None,
        ),
    )
    conn.commit()


@pytest.fixture()
def db(tmp_path: Path):
    database = Database(tmp_path / "avm10b.sqlite3")
    database.initialize()
    yield database
    database.close()


def test_crash_simulated_marks_interrupted_not_abandoned(db: Database, tmp_path: Path) -> None:
    """Job type a31763 : Ripping + finished_at NULL + pas de freaccmd → Interrupted."""
    jid = "a31763eed2ae423eb78ded45b125667a_FIXTURE"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    write_minimal_flac(rip / "01.flac")
    write_minimal_flac(rip / "02.flac")
    _seed_active_rip(db, jid=jid, workdir=wd)

    report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: False)
    assert report.scanned == 1
    assert report.changed_count == 1
    snap_row = db.connect().execute(
        "SELECT state, finished_at, error_summary FROM jobs WHERE id=?", (jid,)
    ).fetchone()
    assert snap_row["state"] == "Interrupted"
    assert snap_row["finished_at"]
    assert "AVM-10B" in snap_row["error_summary"]
    assert "Abandoned" not in snap_row["state"]
    # Fichiers intacts
    assert (rip / "01.flac").is_file()
    assert (rip / "02.flac").is_file()


def test_reconcile_idempotent_repeated_restarts(db: Database, tmp_path: Path) -> None:
    jid = "orphan-repeat"
    wd = tmp_path / jid
    (wd / "rip").mkdir(parents=True)
    _seed_active_rip(db, jid=jid, workdir=wd)
    r1 = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: False)
    r2 = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: False)
    r3 = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: False)
    assert r1.changed_count == 1
    assert r2.scanned == 0  # plus dans actifs non terminés
    assert r3.scanned == 0
    assert list_unfinished_active_jobs(db) == []


def test_freaccmd_running_leaves_uncertain(db: Database, tmp_path: Path) -> None:
    jid = "maybe-alive"
    wd = tmp_path / jid
    wd.mkdir()
    _seed_active_rip(db, jid=jid, workdir=wd)
    report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: True)
    assert report.changed_count == 0
    assert report.actions[0].liveness == LivenessKind.UNCERTAIN
    row = db.connect().execute("SELECT state, finished_at FROM jobs WHERE id=?", (jid,)).fetchone()
    assert row["state"] == "Ripping"
    assert row["finished_at"] is None


def test_alive_lock_pid_is_process_active(db: Database, tmp_path: Path) -> None:
    jid = "lock-alive"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    write_rip_lock(rip, job_id=jid)
    _seed_active_rip(db, jid=jid, workdir=wd)
    report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: False)
    assert report.changed_count == 0
    assert report.actions[0].liveness == LivenessKind.PROCESS_ACTIVE
    clear_rip_lock(rip)


def test_dead_lock_pid_confirms_interrupted(db: Database, tmp_path: Path) -> None:
    jid = "lock-dead"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    lock = rip / LOCK_FILENAME
    lock.write_text(
        json.dumps({"pid": 999_999_991, "job_id": jid, "started_at": _now()}),
        encoding="utf-8",
    )
    _seed_active_rip(db, jid=jid, workdir=wd)
    report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: True)
    # PID mort prime sur freaccmd global
    assert report.changed_count == 1
    assert report.actions[0].liveness == LivenessKind.INTERRUPTED_CONFIRMED


def test_abandon_does_not_delete_files(db: Database, tmp_path: Path) -> None:
    jid = "to-abandon"
    wd = tmp_path / jid / "rip"
    wd.mkdir(parents=True)
    flac = write_minimal_flac(wd / "1.flac")
    before = flac.read_bytes()
    _seed_active_rip(db, jid=jid, workdir=wd.parent)
    reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: False)
    assert mark_job_abandoned(db, jid) is True
    assert mark_job_abandoned(db, jid) is False  # idempotent
    assert flac.read_bytes() == before
    row = db.connect().execute("SELECT state FROM jobs WHERE id=?", (jid,)).fetchone()
    assert row["state"] == "Abandoned"


def test_incomplete_flac_denies_recovery(db: Database, tmp_path: Path) -> None:
    sheet = _approved(2)
    DiscMetadataRepository(db).save(sheet)
    jid = "incomplete"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    write_minimal_flac(rip / "1.flac")
    # piste 2 manquante
    now = _now()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, metadata_id, publish_allowed
        ) VALUES (?, 'Failed', 'Failed', ?, ?, ?, ?, 'x', 'normal', ?, 1)
        """,
        (jid, str(wd), now, now, now, sheet.id),
    )
    conn.commit()
    a = assess_recovery_from_files(
        db, jid, skip_optical_probe=True, allow_offline=True
    )
    assert a.verdict == RecoveryVerdict.DENY
    assert "correspondent" in a.summary_fr.casefold() or "FLAC" in a.summary_fr


def test_missing_metadata_denies_recovery(db: Database, tmp_path: Path) -> None:
    jid = "no-meta"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    write_minimal_flac(rip / "1.flac")
    now = _now()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, metadata_id, publish_allowed
        ) VALUES (?, 'Interrupted', 'Interrupted', ?, ?, ?, ?, 'x', 'technical_test', NULL, 0)
        """,
        (jid, str(wd), now, now, now),
    )
    conn.commit()
    a = assess_recovery_from_files(db, jid, skip_optical_probe=True, allow_offline=True)
    assert a.verdict == RecoveryVerdict.DENY


def test_successful_recovery_preserves_source(db: Database, tmp_path: Path) -> None:
    sheet = _approved(2)
    DiscMetadataRepository(db).save(sheet)
    jid = "recover-ok"
    wd = tmp_path / "src_job"
    rip = wd / "rip"
    rip.mkdir(parents=True)
    originals = [
        write_minimal_flac(rip / "1.flac"),
        write_minimal_flac(rip / "2.flac"),
    ]
    before = [p.read_bytes() for p in originals]
    mtimes = [p.stat().st_mtime for p in originals]
    now = _now()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, metadata_id, publish_allowed, collision_policy
        ) VALUES (?, 'Failed', 'Failed', ?, ?, ?, ?, 'rc', 'normal', ?, 1, 'rename')
        """,
        (jid, str(wd), now, now, now, sheet.id),
    )
    conn.commit()

    lib = tmp_path / "lib"
    jobs = tmp_path / "jobs"
    report = run_recovery_from_files(
        db=db,
        source_job_id=jid,
        library_root=lib,
        jobs_root=jobs,
        confirm_publish=True,
        allow_offline=True,
        skip_optical_probe=True,
        cover_bytes=_JPEG,
    )
    assert report.state.startswith("Completed")
    assert report.job_id != jid
    for p, data, mt in zip(originals, before, mtimes):
        assert p.read_bytes() == data
        assert p.stat().st_mtime == mt
    src = db.connect().execute(
        "SELECT state, error_summary FROM jobs WHERE id=?", (jid,)
    ).fetchone()
    assert src["state"] == "Failed"
    assert report.job_id in (src["error_summary"] or "")


def test_recovery_cancel_midway(db: Database, tmp_path: Path) -> None:
    import threading

    sheet = _approved(2)
    DiscMetadataRepository(db).save(sheet)
    jid = "recover-cancel"
    wd = tmp_path / "src_c"
    rip = wd / "rip"
    rip.mkdir(parents=True)
    write_minimal_flac(rip / "1.flac")
    write_minimal_flac(rip / "2.flac")
    now = _now()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, metadata_id, publish_allowed
        ) VALUES (?, 'Interrupted', 'Interrupted', ?, ?, ?, ?, 'x', 'normal', ?, 1)
        """,
        (jid, str(wd), now, now, now, sheet.id),
    )
    conn.commit()
    cancel = threading.Event()
    cancel.set()
    report = run_recovery_from_files(
        db=db,
        source_job_id=jid,
        library_root=tmp_path / "lib2",
        jobs_root=tmp_path / "jobs2",
        confirm_publish=True,
        allow_offline=True,
        skip_optical_probe=True,
        cover_bytes=_JPEG,
        cancel_event=cancel,
    )
    assert report.state in {"Cancelled", "Interrupted", "Failed"} or report.error
    assert (rip / "1.flac").is_file()


def test_double_recovery_guard(db: Database) -> None:
    assert try_acquire_recovery("job-a")
    assert not try_acquire_recovery("job-b")
    assert recovery_in_progress() == "job-a"
    release_recovery("job-a")
    assert recovery_in_progress() is None
    assert try_acquire_recovery("job-b")
    release_recovery("job-b")


def test_list_job_flac_ignores_temp_and_tagged(tmp_path: Path) -> None:
    rip = tmp_path / "rip"
    rip.mkdir()
    write_minimal_flac(rip / "1.flac")
    (rip / "1.flac.temp").write_bytes(b"")
    tagged = tmp_path / "tagged"
    tagged.mkdir()
    write_minimal_flac(tagged / "1.flac")
    found = list_job_flac_files(tmp_path)
    assert len(found) == 1
    assert found[0].name == "1.flac"


def test_mark_interrupted_never_uses_age_alone(db: Database, tmp_path: Path) -> None:
    """Sans preuve (freaccmd None) → UNCERTAIN, pas Interrupted."""
    jid = "uncertain-age"
    wd = tmp_path / jid
    wd.mkdir()
    _seed_active_rip(db, jid=jid, workdir=wd)
    report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: None)
    assert report.changed_count == 0
    assert report.actions[0].liveness == LivenessKind.UNCERTAIN
