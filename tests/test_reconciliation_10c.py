"""AVM-10C — PID réutilisé, verrou périmé, concurrence interprocessus (simulé)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from audio_video_manager.orchestration.reconciliation import (
    LivenessKind,
    build_job_situation,
    get_job_snapshot,
    reconcile_unfinished_jobs,
    release_recovery,
    try_acquire_recovery,
)
from audio_video_manager.orchestration.rip_lock import (
    LOCK_FILENAME,
    current_process_create_time,
    is_lock_holder_active,
    process_create_time,
    read_rip_lock,
    release_recovery_file_lock,
    try_acquire_recovery_file_lock,
    write_rip_lock,
)
from audio_video_manager.storage import Database


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _seed_ripping(db: Database, jid: str, workdir: Path) -> None:
    now = _now()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            mode, publish_allowed
        ) VALUES (?, 'Ripping', 'Ripping', ?, ?, ?, NULL, 'technical_test', 0)
        """,
        (jid, str(workdir), now, now),
    )
    conn.commit()


@pytest.fixture()
def db(tmp_path: Path):
    database = Database(tmp_path / "avm10c.sqlite3")
    database.initialize()
    yield database
    database.close()


def test_write_lock_stores_create_time(tmp_path: Path) -> None:
    rip = tmp_path / "rip"
    rip.mkdir()
    write_rip_lock(rip, job_id="j1")
    info = read_rip_lock(rip)
    assert info is not None
    assert info.pid == os.getpid()
    ct = current_process_create_time()
    if os.name == "nt":
        assert info.create_time is not None
        assert ct is not None
        assert info.create_time == ct
        assert is_lock_holder_active(info) is True
    else:
        pytest.skip("create_time Windows only — simulé hors NT")


def test_reused_pid_identity_mismatch_treated_as_dead(db: Database, tmp_path: Path) -> None:
    """Simulé : PID courant + create_time faux → identity_ok False → Interrupted."""
    jid = "pid-reuse"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    # Verrou avec notre PID mais create_time impossible (réutilisation simulée)
    fake_ct = 1
    real_ct = current_process_create_time()
    if os.name == "nt" and real_ct is not None:
        assert fake_ct != real_ct
    (rip / LOCK_FILENAME).write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "job_id": jid,
                "started_at": _now(),
                "create_time": fake_ct,
            }
        ),
        encoding="utf-8",
    )
    _seed_ripping(db, jid, wd)
    info = read_rip_lock(wd)
    assert info is not None
    if os.name == "nt" and real_ct is not None:
        assert info.identity_ok is False
        assert info.pid_alive is False  # forcé mort après mismatch
        assert is_lock_holder_active(info) is False
        report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: True)
        assert report.changed_count == 1
        assert report.actions[0].liveness == LivenessKind.INTERRUPTED_CONFIRMED
        snap = get_job_snapshot(db, jid)
        assert snap and snap.state == "Interrupted"
    else:
        pytest.skip("identité PID create_time — Windows requis pour preuve complète")


def test_stale_lock_dead_pid(db: Database, tmp_path: Path) -> None:
    jid = "stale-lock"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    (rip / LOCK_FILENAME).write_text(
        json.dumps(
            {
                "pid": 999_999_992,
                "job_id": jid,
                "started_at": _now(),
                "create_time": 42,
            }
        ),
        encoding="utf-8",
    )
    _seed_ripping(db, jid, wd)
    report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: True)
    assert report.changed_count == 1
    assert report.actions[0].liveness == LivenessKind.INTERRUPTED_CONFIRMED


def test_interprocess_recovery_lock_exclusion(tmp_path: Path) -> None:
    lock_dir = tmp_path / "jobs"
    assert try_acquire_recovery_file_lock(lock_dir, job_id="a") is not None
    assert try_acquire_recovery_file_lock(lock_dir, job_id="b") is None
    release_recovery_file_lock(lock_dir, job_id="a")
    assert try_acquire_recovery_file_lock(lock_dir, job_id="b") is not None
    release_recovery_file_lock(lock_dir, job_id="b")


def test_try_acquire_recovery_uses_file_lock(tmp_path: Path) -> None:
    lock_dir = tmp_path / "jobs2"
    assert try_acquire_recovery("job-1", lock_dir=lock_dir)
    assert not try_acquire_recovery("job-2", lock_dir=lock_dir)
    release_recovery("job-1")
    assert try_acquire_recovery("job-2", lock_dir=lock_dir)
    release_recovery("job-2")


def test_stale_recovery_file_lock_reclaimed(tmp_path: Path) -> None:
    lock_dir = tmp_path / "jobs3"
    lock_dir.mkdir(parents=True)
    path = lock_dir / ".avm-recovery.lock"
    path.write_text(
        json.dumps(
            {
                "pid": 999_999_993,
                "job_id": "old",
                "started_at": _now(),
                "create_time": 7,
            }
        ),
        encoding="utf-8",
    )
    got = try_acquire_recovery_file_lock(lock_dir, job_id="new")
    assert got is not None
    release_recovery_file_lock(lock_dir, job_id="new")


def test_alive_lock_blocks_reconcile(db: Database, tmp_path: Path) -> None:
    jid = "alive-lock"
    wd = tmp_path / jid
    rip = wd / "rip"
    rip.mkdir(parents=True)
    write_rip_lock(rip, job_id=jid)
    _seed_ripping(db, jid, wd)
    sit = build_job_situation(
        get_job_snapshot(db, jid),  # type: ignore[arg-type]
        freaccmd_running=False,
    )
    assert sit.liveness == LivenessKind.PROCESS_ACTIVE
    report = reconcile_unfinished_jobs(db, freaccmd_running_fn=lambda: False)
    assert report.changed_count == 0


@pytest.mark.windows_real
def test_process_create_time_stable_windows() -> None:
    if os.name != "nt":
        pytest.skip("Windows only")
    a = process_create_time(os.getpid())
    b = current_process_create_time()
    assert a is not None and a == b
