"""Worker Qt : pipeline archive hors thread UI (AVM-05)."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.metadata.models import DiscMetadata
from audio_video_manager.metadata.toc_reader import DiscReadResult
from audio_video_manager.orchestration.archive_job import ArchiveJobReport, run_archive_job
from audio_video_manager.storage.database import Database


class ArchiveWorker(QObject):
    progress = Signal(str, object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        metadata: DiscMetadata,
        library_root: Path,
        jobs_root: Path,
        db_path: Path,
        freaccmd: Path | None,
        drive_number: int,
        flac_compression: int,
        eject_after_rip: bool,
        collision_policy: CollisionPolicy,
        confirm_publish: bool,
        optical_device: str | None = None,
        disc_read: DiscReadResult | None = None,
        staged_flac_files: list[Path] | None = None,
        skip_disc_match: bool = False,
        confirmed_rearchive: bool = False,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        self._library_root = library_root
        self._jobs_root = jobs_root
        self._db_path = db_path
        self._freaccmd = freaccmd
        self._drive_number = drive_number
        self._flac_compression = flac_compression
        self._eject_after_rip = eject_after_rip
        self._collision_policy = collision_policy
        self._confirm_publish = confirm_publish
        self._optical_device = optical_device
        self._disc_read = disc_read
        self._staged = staged_flac_files
        self._skip_disc_match = skip_disc_match
        self._confirmed_rearchive = confirmed_rearchive
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

            report: ArchiveJobReport = run_archive_job(
                metadata=self._metadata,
                library_root=self._library_root,
                jobs_root=self._jobs_root,
                freaccmd=self._freaccmd,
                drive_number=self._drive_number,
                db=db,
                flac_compression=self._flac_compression,
                eject_after_rip=self._eject_after_rip,
                collision_policy=self._collision_policy,
                confirm_publish=self._confirm_publish,
                optical_device=self._optical_device,
                disc_read=self._disc_read,
                skip_disc_match=self._skip_disc_match,
                staged_flac_files=self._staged,
                confirmed_rearchive=self._confirmed_rearchive,
                on_progress=on_progress,
                cancel_event=self._cancel,
            )
            db.close()
            self.finished.emit(report)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
