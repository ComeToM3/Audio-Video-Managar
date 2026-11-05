from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from audio_video_manager.extraction.cd_ripper import RipResult
from audio_video_manager.orchestration.rip_job import run_rip_job
from audio_video_manager.storage import Database
from tests.flac_fixtures import write_minimal_flac


def test_run_rip_job_mocked(avm_home: Path, tmp_path: Path) -> None:
    exe = tmp_path / "freaccmd.exe"
    exe.write_text("", encoding="utf-8")
    jobs_root = avm_home / "jobs"
    db = Database(avm_home / "t.sqlite3")
    db.initialize()

    def fake_rip(self, request, *, on_progress=None, cancel_event=None):
        flac = write_minimal_flac(request.workdir / "01.flac")
        if on_progress:
            on_progress("done", 1.0)
        return RipResult(
            success=True,
            cancelled=False,
            returncode=0,
            argv=("freaccmd",),
            stdout="",
            stderr="",
            flac_files=[flac],
            workdir=request.workdir,
        )

    with patch(
        "audio_video_manager.orchestration.rip_job.FreacCdRipper.rip",
        fake_rip,
    ):
        report = run_rip_job(
            freaccmd=exe,
            jobs_root=jobs_root,
            drive_number=0,
            db=db,
            eject_after_rip=False,
        )

    assert report.rip.success is True
    assert len(report.flac_integrity) == 1
    assert report.flac_integrity[0].ok is True
    assert report.rip_check is not None
    assert report.rip_check.status == "weak_ok"
    row = db.connect().execute(
        "SELECT state FROM jobs WHERE id=?", (report.job_id,)
    ).fetchone()
    assert row is not None
    assert row["state"] == "CompletedWithWarnings"
    db.close()
