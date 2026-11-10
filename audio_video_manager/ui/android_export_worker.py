"""Worker Qt for manual Android ADB discovery, inspection, and FLAC export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.library.android_export import (
    AndroidCandidate,
    find_adb_executable,
    list_android_devices,
    scan_android_candidates,
    transfer_android_candidates,
)
from audio_video_manager.storage.database import Database


class AndroidExportWorker(QObject):
    progress = Signal(str, int, int)
    devices_found = Signal(object)
    scan_finished = Signal(object)
    transfer_finished = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        task: str,
        adb_path: Path | None,
        db_path: Path,
        library_root: Path,
        serial: str | None = None,
        candidates: list[AndroidCandidate] | None = None,
    ) -> None:
        super().__init__()
        self._task = task
        self._adb_path = adb_path or find_adb_executable()
        self._db_path = db_path
        self._library_root = library_root
        self._serial = serial
        self._candidates = candidates or []

    @Slot()
    def run(self) -> None:
        db: Database | None = None
        try:
            if self._adb_path is None:
                raise FileNotFoundError("adb.exe introuvable; sélectionnez son chemin.")
            if self._task == "devices":
                self.devices_found.emit(list_android_devices(self._adb_path))
                return
            if not self._serial:
                raise ValueError("Aucun appareil Android sélectionné.")
            db = Database(self._db_path)
            db.connect()
            if self._task == "scan":
                candidates = scan_android_candidates(
                    db,
                    adb_path=self._adb_path,
                    serial=self._serial,
                    library_root=self._library_root,
                    progress=self.progress.emit,
                )
                self.scan_finished.emit(candidates)
            elif self._task == "transfer":
                summary = transfer_android_candidates(
                    db,
                    adb_path=self._adb_path,
                    serial=self._serial,
                    library_root=self._library_root,
                    candidates=self._candidates,
                    progress=self.progress.emit,
                )
                self.transfer_finished.emit(summary)
            else:
                raise ValueError(f"Tâche Android inconnue : {self._task}")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            if db is not None:
                db.close()
            self.finished.emit()