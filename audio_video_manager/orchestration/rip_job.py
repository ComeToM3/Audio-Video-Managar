"""Orchestration rip CD — gate métadonnées en mode archive."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from audio_video_manager.extraction.cd_ripper import (
    FreacCdRipper,
    ProgressCallback,
    RipRequest,
    RipResult,
    create_job_workdir,
)
from audio_video_manager.orchestration.rip_lock import clear_rip_lock, write_rip_lock
from audio_video_manager.logging_setup import get_logger
from audio_video_manager.metadata.enums import JobMode
from audio_video_manager.metadata.models import DiscMetadata
from audio_video_manager.metadata.validation import (
    ApprovalError,
    assert_can_start_archive_rip,
)
from audio_video_manager.storage.database import Database
from audio_video_manager.verification.flac_integrity import (
    FlacIntegrityResult,
    check_many,
)
from audio_video_manager.verification.rip_check import RipCheckResult, evaluate_rip_check

log = get_logger("orchestration.rip_job")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class RipJobReport:
    job_id: str
    workdir: Path
    rip: RipResult
    mode: JobMode
    metadata_id: str | None = None
    flac_integrity: list[FlacIntegrityResult] = field(default_factory=list)
    rip_check: RipCheckResult | None = None


def run_rip_job(
    *,
    freaccmd: Path,
    jobs_root: Path,
    drive_number: int,
    db: Database | None = None,
    flac_compression: int = 5,
    eject_after_rip: bool = False,
    on_progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    mode: JobMode = JobMode.TECHNICAL_TEST,
    metadata: DiscMetadata | None = None,
    allow_library_publish: bool = False,
) -> RipJobReport:
    """
    Lance un rip vers un workdir job (zone A).

    - ``mode=normal`` : exige ``metadata`` Approved (D-011), ``allow_library_publish``
      reste False en AVM-03 (pas de publish C).
    - ``mode=technical_test`` : pas de gate fiche ; publish C interdit.
    """
    if allow_library_publish:
        raise ApprovalError(
            "Utiliser run_archive_job() pour la publication bibliothèque (AVM-05) ; "
            "run_rip_job reste zone A / test technique."
        )

    if mode == JobMode.NORMAL:
        assert_can_start_archive_rip(metadata)
    elif mode == JobMode.TECHNICAL_TEST:
        if metadata is not None and metadata.approval.value == "Approved":
            # Autorisé mais on ignore pour le test ; warn log
            log.warning(
                "Rip technical_test avec fiche Approved — publish C toujours interdit."
            )
    else:
        raise ApprovalError(f"Mode rip inconnu: {mode}")

    job_id, workdir = create_job_workdir(jobs_root)
    started = _utc_now()
    meta_id = metadata.id if metadata else None
    log.info(
        "Job %s mode=%s workdir=%s drive=%s metadata=%s",
        job_id,
        mode.value,
        workdir,
        drive_number,
        meta_id,
    )

    state_start = (
        "AwaitingMetadataApproval"
        if mode == JobMode.NORMAL and (metadata is None or metadata.approval.value != "Approved")
        else "Ripping"
    )
    # Après assert, normal est toujours Approved
    if mode == JobMode.NORMAL:
        state_start = "Ripping"

    if db is not None:
        conn = db.connect()
        conn.execute(
            """
            INSERT INTO jobs(
                id, state, step, workdir, started_at, updated_at,
                mode, metadata_id, publish_allowed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                state_start,
                "Ripping",
                str(workdir),
                started,
                started,
                mode.value,
                meta_id,
                0,
            ),
        )
        conn.commit()

    ripper = FreacCdRipper(freaccmd)
    request = RipRequest(
        freaccmd=Path(freaccmd),
        drive_number=drive_number,
        workdir=workdir,
        flac_compression=flac_compression,
        eject_after_rip=eject_after_rip,
    )
    write_rip_lock(workdir, job_id=job_id)
    try:
        rip = ripper.rip(request, on_progress=on_progress, cancel_event=cancel_event)
    finally:
        clear_rip_lock(workdir)

    integrity = check_many(rip.flac_files)
    rip_check = evaluate_rip_check(
        integrity,
        rip_success=rip.success,
        cancelled=rip.cancelled,
    )

    if rip.cancelled:
        state, step = "Cancelled", "Cancelled"
    elif rip.success and all(i.ok for i in integrity):
        state, step = "CompletedWithWarnings", "RipCheck"
    elif rip.success:
        state, step = "CompletedWithWarnings", "FlacIntegrity"
    else:
        state, step = "Failed", "Ripping"

    finished = _utc_now()
    if db is not None:
        conn = db.connect()
        conn.execute(
            """
            UPDATE jobs
            SET state=?, step=?, updated_at=?, finished_at=?, error_summary=?
            WHERE id=?
            """,
            (
                state,
                step,
                finished,
                finished,
                rip.error or (rip_check.summary if rip_check else None),
                job_id,
            ),
        )
        conn.execute(
            """
            INSERT INTO job_checkpoints(job_id, step, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                step,
                (
                    f'{{"flac_count": {len(rip.flac_files)}, '
                    f'"rip_check": "{rip_check.status if rip_check else None}", '
                    f'"mode": "{mode.value}"}}'
                ),
                finished,
            ),
        )
        conn.commit()

    return RipJobReport(
        job_id=job_id,
        workdir=workdir,
        rip=rip,
        mode=mode,
        metadata_id=meta_id,
        flac_integrity=integrity,
        rip_check=rip_check,
    )
