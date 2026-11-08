"""Finalisation d'une vidéo hors du thread d'interface."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.library.video_archive import finalize_video, reconcile_video
from audio_video_manager.storage.database import Database


class VideoFinalizeWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, db_path: Path, source: str, destination: str, ffmpeg: str) -> None:
        super().__init__()
        self._db_path = db_path
        self._source = source
        self._destination = destination
        self._ffmpeg = ffmpeg

    @Slot()
    def run(self) -> None:
        db = Database(self._db_path)
        try:
            executable = self._ffmpeg or shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
            if not executable:
                raise FileNotFoundError("Configurez FFmpeg dans Paramètres.")
            finalize_video(db, Path(self._source), Path(self._destination), Path(executable))
            db.close()
            self.finished.emit(self._destination)
        except Exception as exc:
            db.close()
            self.failed.emit(str(exc))


class VideoReconcileWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, db_path: Path, video_id: int) -> None:
        super().__init__()
        self._db_path = db_path
        self._video_id = video_id

    @Slot()
    def run(self) -> None:
        db = Database(self._db_path)
        try:
            reconcile_video(db, self._video_id)
            db.close()
            self.finished.emit(self._video_id)
        except Exception as exc:
            db.close()
            self.failed.emit(str(exc))