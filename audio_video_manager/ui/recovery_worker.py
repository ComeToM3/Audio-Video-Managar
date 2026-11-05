"""Worker Qt — reprise contrôlée depuis FLAC existants (AVM-10B)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.orchestration.archive_job import ArchiveJobReport
from audio_video_manager.orchestration.reconciliation import run_recovery_from_files
from audio_video_manager.storage.database import Database


class RecoveryWorker(QObject):
    progress = Signal(str, object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        source_job_id: str,
        library_root: Path,
        jobs_root: Path,
        db_path: Path,
        collision_policy: CollisionPolicy = CollisionPolicy.RENAME,
        confirm_publish: bool = True,
        confirmed_rearchive: bool = False,
        allow_offline: bool = False,
        optical_device: str | None = None,
        skip_optical_probe: bool = False,
    ) -> None:
        super().__init__()
        self._source_job_id = source_job_id
        self._library_root = library_root
        self._jobs_root = jobs_root
        self._db_path = db_path
        self._collision_policy = collision_policy
        self._confirm_publish = confirm_publish
        self._confirmed_rearchive = confirmed_rearchive
        self._allow_offline = allow_offline
        self._optical_device = optical_device
        self._skip_optical_probe = skip_optical_probe
        self._cancel = threading.Event()

    @Slot()
    def cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            db = Database(self._db_path)
            db.initialize()

            def on_progress(message: str, fraction: float | None) -> None:
                self.progress.emit(message, fraction)

            report: ArchiveJobReport = run_recovery_from_files(
                db=db,
                source_job_id=self._source_job_id,
                library_root=self._library_root,
                jobs_root=self._jobs_root,
                collision_policy=self._collision_policy,
                confirm_publish=self._confirm_publish,
                confirmed_rearchive=self._confirmed_rearchive,
                allow_offline=self._allow_offline,
                optical_device=self._optical_device,
                skip_optical_probe=self._skip_optical_probe,
                on_progress=on_progress,
                cancel_event=self._cancel,
            )
            db.close()
            self.finished.emit(report)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
