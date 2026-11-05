"""Worker Qt : rip hors thread UI."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.metadata.enums import JobMode
from audio_video_manager.metadata.models import DiscMetadata
from audio_video_manager.orchestration.rip_job import RipJobReport, run_rip_job
from audio_video_manager.storage.database import Database


class RipWorker(QObject):
    progress = Signal(str, object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        freaccmd: Path,
        jobs_root: Path,
        drive_number: int,
        db_path: Path,
        flac_compression: int,
        eject_after_rip: bool,
        mode: JobMode = JobMode.TECHNICAL_TEST,
        metadata: DiscMetadata | None = None,
    ) -> None:
        super().__init__()
        self._freaccmd = freaccmd
        self._jobs_root = jobs_root
        self._drive_number = drive_number
        self._db_path = db_path
        self._flac_compression = flac_compression
        self._eject_after_rip = eject_after_rip
        self._mode = mode
        self._metadata = metadata
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

            report: RipJobReport = run_rip_job(
                freaccmd=self._freaccmd,
                jobs_root=self._jobs_root,
                drive_number=self._drive_number,
                db=db,
                flac_compression=self._flac_compression,
                eject_after_rip=self._eject_after_rip,
                on_progress=on_progress,
                cancel_event=self._cancel,
                mode=self._mode,
                metadata=self._metadata,
                allow_library_publish=False,
            )
            db.close()
            self.finished.emit(report)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
