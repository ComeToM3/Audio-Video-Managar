"""Worker PySide6 pour inspection et extraction DVD hors thread UI."""

from __future__ import annotations

import os
import threading
import shutil
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from audio_video_manager.config import AppConfig
from audio_video_manager.extraction.dvd import DvdInspector
from audio_video_manager.extraction.dvd_extractor import (
    DvdExtractionCancelled,
    DvdExtractionService,
)
from audio_video_manager.metadata.video import VideoInspectionStatus


class DvdTaskWorker(QObject):
    progress = Signal(str, object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        config: AppConfig,
        task: str,
        source: str,
        destination: str = "",
        title_index: int = 0,
        angle_index: int = 1,
        audio_stream_indices: tuple[int, ...] = (),
        confirmed: bool = False,
        rights_attested: bool = False,
        allow_pcm_conversion: bool = False,
        db_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._task = task
        self._source = source
        self._destination = destination
        self._title_index = title_index
        self._angle_index = angle_index
        self._audio_stream_indices = audio_stream_indices
        self._confirmed = confirmed
        self._rights_attested = rights_attested
        self._allow_pcm_conversion = allow_pcm_conversion
        self._db_path = db_path
        self._reservation_id: int | None = None
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def _inspector(self) -> DvdInspector:
        raw_ffmpeg = (
            (self._config.ffmpeg_path or "").strip()
            or os.environ.get("AVM_FFMPEG", "").strip()
            or shutil.which("ffmpeg")
            or shutil.which("ffmpeg.exe")
            or ""
        )
        ffprobe_path: Path | None = None
        if raw_ffmpeg:
            ffmpeg = Path(raw_ffmpeg).expanduser()
            sibling = ffmpeg.with_name("ffprobe.exe" if ffmpeg.suffix.casefold() == ".exe" else "ffprobe")
            ffprobe_path = sibling
        return DvdInspector(
            ffprobe_path=ffprobe_path,
            dvdnav_directory=(self._config.dvdnav_library_dir or None),
        )

    def _service(self, inspector: DvdInspector) -> DvdExtractionService:
        return DvdExtractionService(
            ffmpeg_path=(self._config.ffmpeg_path or None),
            inspector=inspector,
        )

    def _index_published(self, path: Path, service: DvdExtractionService) -> None:
        from audio_video_manager.library.video_archive import index_published_video
        from audio_video_manager.storage.database import Database

        if self._db_path is None:
            raise RuntimeError("Catalogue indisponible; le fichier publié est conservé.")
        if service._ffmpeg_path is None:
            raise RuntimeError("FFmpeg introuvable pour valider le fichier publié.")

        def decode(argv: list[str], duration: float) -> tuple[int, str]:
            argv[1:1] = ["-progress", "pipe:1", "-stats_period", "0.5"]
            return service._run_monitored(
                argv, duration_seconds=duration, cancel_event=self._cancel,
                on_progress=self.progress.emit, phase="Validation locale",
                fraction_start=0.85, fraction_span=0.13,
                working_directory=path.parent,
            )

        db = Database(self._db_path)
        try:
            if self._reservation_id is None:
                row = db.connect().execute(
                    "SELECT id, sha256 FROM videos WHERE path = ? AND publication_state = 'pending'",
                    (str(path.resolve()),),
                ).fetchone()
                if row is not None and row["sha256"].startswith("intent:"):
                    self._reservation_id = int(row["id"])
            index_published_video(
                db, path, service._ffmpeg_path, cancel_event=self._cancel,
                on_progress=self.progress.emit, decode_runner=decode, reservation_id=self._reservation_id,
            )
        finally:
            db.close()

    def _reserve_publication(self, destination: Path) -> int:
        from audio_video_manager.library.video_archive import reserve_dvd_publication
        from audio_video_manager.storage.database import Database

        if self._db_path is None:
            raise RuntimeError("Catalogue indisponible; extraction non démarrée.")
        db = Database(self._db_path)
        try:
            return reserve_dvd_publication(db, destination)
        finally:
            db.close()

    def _clear_missing_reservation(self) -> None:
        from audio_video_manager.library.video_archive import remove_missing_pending_video
        from audio_video_manager.storage.database import Database

        if self._db_path is None or self._reservation_id is None:
            return
        db = Database(self._db_path)
        try:
            remove_missing_pending_video(db, self._reservation_id)
        finally:
            db.close()

    @Slot()
    def run(self) -> None:
        try:
            inspector = self._inspector()
            if self._task == "index":
                self._index_published(Path(self._source), self._service(inspector))
                self.finished.emit(Path(self._source))
                return
            if self._task == "inspect":
                self.progress.emit("Inspection DVD en lecture seule…", 0.0)
                result = inspector.inspect(self._source)
                if result.status not in (
                    VideoInspectionStatus.TITLE_SELECTION_REQUIRED,
                    VideoInspectionStatus.INSPECTED,
                ):
                    raise RuntimeError(result.diagnostic or "Le DVD n’a pas pu être inspecté.")
                self.finished.emit(result)
                return
            if self._task == "inspect_title":
                self.progress.emit("Lecture des pistes du titre…", 0.0)
                result = inspector.inspect(
                    self._source,
                    title_indices=(self._title_index,),
                    angle_index=self._angle_index,
                )
                if result.status != VideoInspectionStatus.INSPECTED or not result.titles:
                    raise RuntimeError(
                        result.diagnostic or "Les pistes du titre n’ont pas pu être inspectées."
                    )
                self.finished.emit(result.titles[0])
                return
            if self._cancel.is_set():
                raise DvdExtractionCancelled("Opération DVD annulée avant le préflight.")
            service = self._service(inspector)
            plan = service.prepare(self._source, self._destination)
            self._reservation_id = self._reserve_publication(Path(self._destination))

            def on_progress(message: str, fraction: float | None) -> None:
                self.progress.emit(message, None if fraction is None else fraction * 0.85)

            try:
                if self._task == "mkv":
                    result = service.extract(
                        plan,
                        title_index=self._title_index,
                        angle_index=self._angle_index,
                        confirmed=self._confirmed,
                        rights_attested=self._rights_attested,
                        allow_pcm_conversion=self._allow_pcm_conversion,
                        cancel_event=self._cancel,
                        on_progress=on_progress,
                    )
                elif self._task == "audio":
                    result = service.extract_audio(
                        plan,
                        title_index=self._title_index,
                        angle_index=self._angle_index,
                        audio_stream_indices=self._audio_stream_indices,
                        confirmed=self._confirmed,
                        rights_attested=self._rights_attested,
                        allow_pcm_conversion=self._allow_pcm_conversion,
                        cancel_event=self._cancel,
                        on_progress=on_progress,
                    )
                else:
                    raise ValueError(f"Tâche DVD inconnue : {self._task}")
            except Exception as extraction_error:
                try:
                    self._clear_missing_reservation()
                except Exception as recovery_error:  # noqa: BLE001
                    raise RuntimeError(
                        f"{extraction_error} ; une entrée en attente peut nécessiter une vérification "
                        f"dans la bibliothèque : {recovery_error}"
                    ) from extraction_error
                raise
            try:
                self._index_published(result.output_path, service)
                result = replace(result, cataloged=True)
            except Exception as exc:  # noqa: BLE001
                result = replace(result, catalog_error=str(exc))
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))