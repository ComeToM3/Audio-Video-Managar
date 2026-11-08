"""Panneau d’inspection et d’extraction DVD-Video."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.config import AppConfig
from audio_video_manager.extraction.dvd import DvdInspector
from audio_video_manager.extraction.dvd_extractor import (
    DvdExtractionResult,
    DvdExtractionService,
)
from audio_video_manager.metadata.video import (
    DvdInspectionResult,
    DvdTitleInspection,
    VideoInspectionStatus,
)
from audio_video_manager.ui.dvd_worker import DvdTaskWorker
from audio_video_manager.ui.thread_lifecycle import (
    attach_worker_thread,
    shutdown_worker_thread,
)


def _format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "durée inconnue"
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}"
    return f"{minutes:02d}:{whole_seconds:02d}"


def _optical_drive_roots() -> list[str]:
    if os.name != "nt":
        return []
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetLogicalDrives.restype = ctypes.c_uint32
        kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
        kernel.GetDriveTypeW.restype = ctypes.c_uint32
        mask = kernel.GetLogicalDrives()
        return [
            f"{chr(65 + index)}:\\"
            for index in range(26)
            if mask & (1 << index)
            and kernel.GetDriveTypeW(f"{chr(65 + index)}:\\") == 5
        ]
    except (AttributeError, OSError):
        return []


class DvdArchivePanel(QWidget):
    """Contrôles DVD intégrés à l’assistant Archiver."""

    busy_changed = Signal(bool)
    extraction_finished = Signal()
    finalize_existing_requested = Signal()
    catalog_changed = Signal()
    open_library_requested = Signal()

    def __init__(self, config: AppConfig, parent=None, *, db_path: Path | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._db_path = db_path
        self._worker: DvdTaskWorker | None = None
        self._thread = None
        self._inspection: DvdInspectionResult | None = None
        self._title_inspection: DvdTitleInspection | None = None
        self._task_kind: str | None = None
        self._result_path: Path | None = None
        self._cataloged = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        source_box = QGroupBox("Source")
        source_form = QFormLayout(source_box)
        source_row = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.setEditable(True)
        self.source_combo.setAccessibleName("Lecteur ou dossier DVD-Video")
        self.source_combo.setMinimumWidth(0)
        for root_path in _optical_drive_roots():
            self.source_combo.addItem(root_path, root_path)
        self.source_combo.currentTextChanged.connect(self._invalidate_inspection)
        refresh_drives = QPushButton("Actualiser")
        refresh_drives.setAccessibleName("Actualiser les lecteurs optiques")
        refresh_drives.clicked.connect(self._refresh_drives)
        browse_source = QPushButton("Parcourir")
        browse_source.clicked.connect(self._browse_source)
        source_row.addWidget(self.source_combo, 1)
        source_row.addWidget(refresh_drives)
        source_row.addWidget(browse_source)
        source_form.addRow("Lecteur / dossier :", source_row)
        self.btn_inspect = QPushButton("Inspecter le DVD")
        self.btn_inspect.setProperty("primary", True)
        self.btn_inspect.clicked.connect(self._inspect)
        source_form.addRow("", self.btn_inspect)
        self.btn_finalize_existing = QPushButton("Finaliser un MKV existant…")
        self.btn_finalize_existing.clicked.connect(self.finalize_existing_requested.emit)
        source_form.addRow("", self.btn_finalize_existing)
        self.pages = QStackedWidget()
        source_page = QWidget()
        source_layout = QVBoxLayout(source_page)
        source_layout.addWidget(source_box)
        source_layout.addStretch(1)
        self.pages.addWidget(source_page)

        title_box = QGroupBox("Titres et pistes")
        title_form = QFormLayout(title_box)
        self.title_combo = QComboBox()
        self.title_combo.setAccessibleName("Titre DVD-Video")
        self.title_combo.setEnabled(False)
        self.title_combo.currentIndexChanged.connect(self._on_title_changed)
        title_form.addRow("Titre :", self.title_combo)
        angle_row = QHBoxLayout()
        self.angle_spin = QSpinBox()
        self.angle_spin.setRange(1, 1)
        self.angle_spin.setEnabled(False)
        self.angle_spin.setAccessibleName("Angle DVD-Video")
        self.angle_spin.valueChanged.connect(self._on_angle_changed)
        angle_row.addWidget(self.angle_spin)
        self.btn_probe_title = QPushButton("Lire les pistes")
        self.btn_probe_title.setEnabled(False)
        self.btn_probe_title.clicked.connect(self._inspect_selected_title)
        angle_row.addWidget(self.btn_probe_title)
        angle_row.addStretch(1)
        title_form.addRow("Angle :", angle_row)
        self.stream_summary = QLabel("Les titres et pistes ne sont pas encore inspectés.")
        self.stream_summary.setWordWrap(True)
        self.stream_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_form.addRow("Flux vidéo / sous-titres :", self.stream_summary)
        self.chapter_list = QListWidget()
        self.chapter_list.setAccessibleName("Chapitres du titre inspecté")
        self.chapter_list.setMaximumHeight(100)
        self.chapter_list.hide()
        title_form.addRow("Chapitres :", self.chapter_list)
        self.audio_list = QListWidget()
        self.audio_list.setAccessibleName("Pistes audio à extraire")
        self.audio_list.setMaximumHeight(120)
        self.audio_list.itemChanged.connect(self._on_audio_item_changed)
        self.audio_list.setEnabled(False)
        self.audio_list.hide()
        title_page = QWidget()
        title_layout = QVBoxLayout(title_page)
        title_layout.addWidget(title_box)
        title_layout.addStretch(1)
        title_scroll = QScrollArea()
        title_scroll.setWidgetResizable(True)
        title_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        title_scroll.setWidget(title_page)
        self.pages.addWidget(title_scroll)

        operation_box = QGroupBox("Opération")
        operation_row = QHBoxLayout(operation_box)
        self.radio_master = QRadioButton("MKV maître complet")
        self.radio_audio = QRadioButton("Audio seulement (MKA)")
        self.radio_master.setChecked(True)
        self.radio_master.toggled.connect(self._on_operation_changed)
        self.radio_audio.toggled.connect(self._on_operation_changed)
        operation_row.addWidget(self.radio_master)
        operation_row.addWidget(self.radio_audio)
        operation_row.addStretch(1)
        extraction_page = QWidget()
        extraction_layout = QVBoxLayout(extraction_page)
        extraction_layout.addWidget(operation_box)
        self.audio_label = QLabel("Pistes audio à extraire :")
        self.audio_label.hide()
        extraction_layout.addWidget(self.audio_label)
        extraction_layout.addWidget(self.audio_list)

        destination_box = QGroupBox("Destination")
        destination_form = QFormLayout(destination_box)
        destination_row = QHBoxLayout()
        self.destination_edit = QLineEdit()
        self.destination_edit.setAccessibleName("Fichier de destination MKV ou MKA")
        self.destination_edit.setPlaceholderText("Choisissez un nouveau fichier .mkv ou .mka")
        self.destination_edit.textChanged.connect(self._update_start_enabled)
        browse_destination = QPushButton("Parcourir")
        browse_destination.clicked.connect(self._browse_destination)
        destination_row.addWidget(self.destination_edit, 1)
        destination_row.addWidget(browse_destination)
        destination_form.addRow("Fichier :", destination_row)
        extraction_layout.addWidget(destination_box)

        self.pcm_check = QCheckBox("Autoriser la conversion PCM DVD 16 bits sans perte")
        self.pcm_check.setAccessibleName("Autoriser la conversion PCM DVD sans perte")
        self.pcm_check.stateChanged.connect(self._update_start_enabled)
        self.pcm_check.hide()
        extraction_layout.addWidget(self.pcm_check)

        self.rights_check = QCheckBox(
            "Je confirme mes droits ou une autorisation de reproduction."
        )
        self.rights_check.setAccessibleName("Confirmer les droits de reproduction")
        self.rights_check.stateChanged.connect(self._update_start_enabled)
        extraction_layout.addWidget(self.rights_check)
        extraction_layout.addStretch(1)
        extraction_scroll = QScrollArea()
        extraction_scroll.setWidgetResizable(True)
        extraction_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        extraction_scroll.setWidget(extraction_page)
        self.pages.addWidget(extraction_scroll)
        root.addWidget(self.pages, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.status_label = QLabel("Prêt. Configurez FFmpeg et libdvdnav dans Paramètres si nécessaire.")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_open_result = QPushButton("Ouvrir le dossier")
        self.btn_open_result.setEnabled(False)
        self.btn_open_result.clicked.connect(self._open_result_folder)
        buttons.addWidget(self.btn_open_result)
        self.btn_open_library = QPushButton("Voir dans la bibliothèque")
        self.btn_open_library.clicked.connect(self.open_library_requested.emit)
        self.btn_open_library.hide()
        buttons.addWidget(self.btn_open_library)
        self.btn_retry_index = QPushButton("Réessayer l’indexation")
        self.btn_retry_index.clicked.connect(self._retry_index)
        self.btn_retry_index.hide()
        buttons.addWidget(self.btn_retry_index)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self._cancel_or_close)
        buttons.addWidget(self.btn_cancel)
        self.btn_start = QPushButton("Démarrer l’extraction…")
        self.btn_start.setProperty("primary", True)
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start_extraction)
        buttons.addWidget(self.btn_start)
        root.addLayout(buttons)
        self.btn_start.hide()
        self.btn_cancel.hide()

    def set_config(self, config: AppConfig) -> None:
        self._config = config

    def set_step(self, step: int) -> None:
        self.pages.setCurrentIndex(min(step, 2))
        self.pages.setVisible(step < 4)
        self.progress.setVisible(step >= 3 or self._thread is not None)
        self.btn_cancel.setVisible(self._thread is not None)
        self.btn_open_result.setVisible(step == 4)
        self.btn_open_library.setVisible(step == 4 and self._cataloged)

    def shutdown_background_work(self, *, timeout_ms: int = 12_000) -> bool:
        return shutdown_worker_thread(self._thread, self._worker, timeout_ms=timeout_ms)

    def _refresh_drives(self) -> None:
        current = self.source_combo.currentText().strip()
        roots = _optical_drive_roots()
        self.source_combo.clear()
        self.source_combo.addItems(roots)
        self.source_combo.setEditText(current or (roots[0] if roots else ""))
        if not roots:
            self.status_label.setText("Aucun lecteur optique détecté; vous pouvez choisir un dossier VIDEO_TS.")

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choisir la structure DVD-Video")
        if path:
            self.source_combo.setEditText(path)

    def _browse_destination(self) -> None:
        suffix = ".mka" if self.radio_audio.isChecked() else ".mkv"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Destination DVD",
            self.destination_edit.text() or str(Path(self._config.library_root) / f"DVD-master{suffix}"),
            "Matroska (*.mkv *.mka)",
        )
        if selected:
            path = Path(selected)
            if path.suffix.casefold() not in {".mkv", ".mka"}:
                path = path.with_suffix(suffix)
            self.destination_edit.setText(str(path))

    def _suggest_destination(self) -> None:
        if self.destination_edit.text().strip():
            return
        root = Path(self._config.library_root).expanduser()
        if not root.is_absolute() or not root.is_dir():
            return
        extension = ".mka" if self.radio_audio.isChecked() else ".mkv"
        for number in range(1, 1000):
            suffix = "" if number == 1 else f"-{number}"
            candidate = root / f"DVD-master{suffix}{extension}"
            if not candidate.exists() and not candidate.is_symlink():
                self.destination_edit.setText(str(candidate))
                return

    def _on_operation_changed(self, *_args: object) -> None:
        audio_mode = self.radio_audio.isChecked()
        has_title_details = self._title_inspection is not None
        self.audio_list.setVisible(has_title_details)
        self.audio_label.setVisible(has_title_details)
        self.audio_list.setEnabled(audio_mode and has_title_details)
        destination = self.destination_edit.text().strip()
        if destination:
            path = Path(destination)
            desired = ".mka" if audio_mode else ".mkv"
            if path.suffix.casefold() in {".mkv", ".mka"} and path.suffix.casefold() != desired:
                self.destination_edit.setText(str(path.with_suffix(desired)))
        self._update_start_enabled()

    def _inspection_error(self, result: DvdInspectionResult) -> str:
        if not result.title_candidates:
            return result.diagnostic or "Aucun titre DVD-Video n’a été trouvé."
        return ""

    def _inspect(self) -> None:
        source = self.source_combo.currentText().strip()
        if not source:
            self.status_label.setText("Choisissez un lecteur ou un dossier DVD-Video.")
            return
        self._inspection = None
        self._title_inspection = None
        self.pcm_check.setChecked(False)
        self.title_combo.clear()
        self.audio_list.clear()
        self.audio_list.hide()
        self.audio_label.hide()
        self.chapter_list.clear()
        self.chapter_list.hide()
        self._title_inspection = None
        self.stream_summary.setText("Inspection DVD en cours…")
        self._start_worker(task="inspect", source=source)

    def _selected_title(self) -> int | None:
        value = self.title_combo.currentData()
        return int(value) if value is not None else None

    def _on_title_changed(self, *_args: object) -> None:
        self._title_inspection = None
        self.pcm_check.setChecked(False)
        self.pcm_check.hide()
        self.audio_list.clear()
        self.audio_list.hide()
        self.audio_label.hide()
        self.chapter_list.clear()
        self.chapter_list.hide()
        self.stream_summary.setText("Sélectionnez le titre et l’angle, puis lisez ses pistes.")
        selected_title = self._selected_title()
        candidate = next(
            (
                item
                for item in (self._inspection.title_candidates if self._inspection else ())
                if item.title_index == selected_title
            ),
            None,
        )
        self.angle_spin.blockSignals(True)
        self.angle_spin.setRange(1, max(1, candidate.angle_count or 1) if candidate else 1)
        self.angle_spin.setValue(1)
        self.angle_spin.blockSignals(False)
        self.angle_spin.setEnabled(candidate is not None)
        self.btn_probe_title.setEnabled(candidate is not None)
        self._update_start_enabled()

    def _on_angle_changed(self, *_args: object) -> None:
        self._title_inspection = None
        self.pcm_check.setChecked(False)
        self.pcm_check.hide()
        self.audio_list.clear()
        self.audio_list.hide()
        self.audio_label.hide()
        self.chapter_list.clear()
        self.chapter_list.hide()
        self.stream_summary.setText("L’angle a changé; relisez les pistes avant extraction.")
        self._update_start_enabled()

    def _invalidate_inspection(self, *_args: object) -> None:
        if self._thread is not None:
            return
        self._inspection = None
        self._title_inspection = None
        self.pcm_check.setChecked(False)
        self.pcm_check.hide()
        self.title_combo.clear()
        self.title_combo.setEnabled(False)
        self.angle_spin.setEnabled(False)
        self.btn_probe_title.setEnabled(False)
        self.audio_list.clear()
        self.audio_list.hide()
        self.audio_label.hide()
        self.chapter_list.clear()
        self.chapter_list.hide()
        self.stream_summary.setText("La source a changé; inspectez le DVD de nouveau.")
        self._update_start_enabled()

    def _on_audio_item_changed(self, _item: QListWidgetItem) -> None:
        self._update_start_enabled()

    def _inspect_selected_title(self) -> None:
        title_index = self._selected_title()
        if title_index is None:
            return
        self._title_inspection = None
        self.audio_list.clear()
        self.stream_summary.setText("Lecture des pistes du titre…")
        self._start_worker(
            task="inspect_title",
            source=self.source_combo.currentText().strip(),
            title_index=title_index,
            angle_index=self.angle_spin.value(),
        )

    def _start_worker(
        self,
        *,
        task: str,
        source: str,
        destination: str = "",
        title_index: int = 0,
        angle_index: int = 1,
        audio_stream_indices: tuple[int, ...] = (),
    ) -> None:
        if self._thread is not None:
            return
        worker = DvdTaskWorker(
            config=self._config,
            task=task,
            source=source,
            destination=destination,
            title_index=title_index,
            angle_index=angle_index,
            audio_stream_indices=audio_stream_indices,
            confirmed=True,
            rights_attested=(
                self.rights_check.isChecked() if task in {"mkv", "audio"} else False
            ),
            allow_pcm_conversion=self.pcm_check.isChecked(),
            db_path=self._db_path,
        )
        self._worker = worker
        self._task_kind = task
        self.progress.setValue(0)
        self.btn_inspect.setEnabled(False)
        self.btn_probe_title.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_cancel.setText("Annuler l’opération")
        self._thread = attach_worker_thread(
            worker,
            on_finished=self._on_worker_finished,
            on_failed=self._on_worker_failed,
            on_cleared=self._on_worker_cleared,
            progress_slot=self._on_progress,
        )
        self.pages.setEnabled(False)
        self.btn_cancel.show()
        self.busy_changed.emit(True)
        self._thread.start()

    def _populate_inspection(self, result: DvdInspectionResult) -> None:
        self._inspection = result
        self._suggest_destination()
        self.title_combo.blockSignals(True)
        self.title_combo.clear()
        suggestion = DvdExtractionService._suggested_title(result.title_candidates)
        for candidate in result.title_candidates:
            note = " · Suggestion durée" if candidate.title_index == suggestion else ""
            label = (
                f"Titre {candidate.title_index}{note} · "
                f"{_format_duration(candidate.duration_seconds)} · "
                f"{len(candidate.chapters)} chapitres · {candidate.angle_count or '?'} angle(s)"
            )
            self.title_combo.addItem(label, candidate.title_index)
        if suggestion is not None:
            self.title_combo.setCurrentIndex(
                self.title_combo.findData(suggestion)
            )
            suggested_candidate = next(
                item for item in result.title_candidates if item.title_index == suggestion
            )
            self.angle_spin.setRange(1, max(1, suggested_candidate.angle_count or 1))
            self.angle_spin.setValue(1)
        self.title_combo.blockSignals(False)
        self._on_title_changed()
        self.title_combo.setEnabled(bool(result.title_candidates))
        self.angle_spin.setEnabled(bool(result.title_candidates))
        self.btn_probe_title.setEnabled(
            self._thread is None and bool(result.title_candidates)
        )
        self.stream_summary.setText(
            f"{len(result.title_candidates)} titre(s) trouvés; suggestion par durée uniquement. "
            "Lisez les pistes du titre choisi avant de lancer une extraction."
        )
        self.status_label.setText(
            result.diagnostic or "Inspection terminée; confirmez le titre et l’angle avant extraction."
        )
        self.progress.setValue(0)

    def _populate_title_inspection(self, title: DvdTitleInspection) -> None:
        self._title_inspection = title
        video = [
            f"Vidéo {stream.codec_name or 'inconnue'} {stream.width or '?'}×{stream.height or '?'}"
            for stream in title.video_streams
        ]
        subtitles = [
            f"Sous-titre {stream.codec_name or 'inconnu'} · {stream.language or 'langue inconnue'}"
            for stream in title.subtitle_streams
        ]
        self.stream_summary.setText("\n".join(video + subtitles) or "Aucun flux vidéo/sous-titre détecté.")
        self.chapter_list.clear()
        for chapter in title.chapters:
            start = _format_duration(chapter.start_seconds)
            end = _format_duration(chapter.end_seconds)
            label = f"Chapitre {chapter.index} · {start}–{end}"
            if chapter.title:
                label += f" · {chapter.title}"
            self.chapter_list.addItem(label)
        self.chapter_list.setVisible(bool(title.chapters))
        self.audio_list.clear()
        self.audio_list.setVisible(True)
        self.audio_label.setVisible(True)
        missing_indices = 0
        selectable_audio = [stream for stream in title.audio_streams if stream.index is not None]
        for stream in title.audio_streams:
            if stream.index is None:
                missing_indices += 1
                continue
            details = [stream.codec_name or "codec inconnu", stream.language or "langue inconnue"]
            if stream.channels:
                details.append(f"{stream.channels} ch")
            if stream.sample_rate:
                details.append(f"{stream.sample_rate} Hz")
            item = QListWidgetItem(f"Piste {stream.index}: " + " · ".join(details))
            item.setData(Qt.ItemDataRole.UserRole, stream.index)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if len(selectable_audio) == 1 else Qt.CheckState.Unchecked)
            self.audio_list.addItem(item)
        self.audio_list.setEnabled(self.radio_audio.isChecked())
        self.pcm_check.setVisible(any(stream.codec_name == "pcm_dvd" for stream in title.audio_streams))
        self.pcm_check.setChecked(False)
        if missing_indices:
            self.status_label.setText(
                f"{missing_indices} piste(s) audio sans index exploitable; elles ne peuvent pas être sélectionnées."
            )
        self.btn_probe_title.setEnabled(True)
        self.status_label.setText(
            f"Titre {title.title_index}, angle {title.angle_index}, "
            f"{_format_duration(title.duration_seconds)} : "
            f"{len(title.audio_streams)} piste(s) audio, {len(title.subtitle_streams)} sous-titre(s), "
            f"{len(title.chapters)} chapitre(s)."
        )
        self._update_start_enabled()

    def _on_worker_finished(self, result: object) -> None:
        if isinstance(result, DvdInspectionResult):
            error = self._inspection_error(result)
            if error:
                self._inspection = None
                self.status_label.setText(error)
            else:
                self._populate_inspection(result)
            return
        if isinstance(result, DvdTitleInspection):
            self._populate_title_inspection(result)
            return
        if isinstance(result, DvdExtractionResult):
            self._result_path = result.output_path
            self._cataloged = result.cataloged
            tracks = ", ".join(
                f"{stream.codec_name or 'audio'} {stream.language or ''}".strip()
                for stream in result.streams
            )
            self.status_label.setText(
                f"Fichier publié : {result.output_path}\n"
                f"Durée {_format_duration(result.duration_seconds)} · "
                f"{result.chapter_count} chapitres · {result.size_bytes:,} octets\n{tracks}"
                + ("\n" + "\n".join(result.warnings) if result.warnings else "")
                + ("\nAjouté à la bibliothèque; fidélité complète à la source non établie."
                   if result.cataloged else f"\nNon indexé : {result.catalog_error or 'catalogue indisponible'}")
            )
            self.btn_retry_index.setVisible(not result.cataloged)
            self.btn_retry_index.setEnabled(self._thread is None)
            self.btn_open_library.setEnabled(self._thread is None)
            self.btn_open_result.setEnabled(True)
            self.progress.setValue(100 if result.cataloged else 85)
            self.catalog_changed.emit()
            self.extraction_finished.emit()
            return
        if isinstance(result, Path) and self._task_kind == "index":
            self._result_path = result
            self._cataloged = True
            self.btn_retry_index.hide()
            self.btn_open_library.show()
            self.btn_open_library.setEnabled(self._thread is None)
            self.progress.setValue(100)
            self.status_label.setText(f"Ajouté à la bibliothèque : {result}\nFidélité complète à la source non établie.")
            self.catalog_changed.emit()

    def _on_worker_failed(self, message: str) -> None:
        self.status_label.setText(f"Opération non terminée : {message}")
        self.progress.setValue(0)
        if self._task_kind == "index" and self._result_path is not None:
            self.status_label.setText(f"Fichier conservé : {self._result_path}\nIndexation non terminée : {message}")
            self.btn_retry_index.show()
            self.btn_retry_index.setEnabled(self._thread is None)
            self.catalog_changed.emit()

    def _on_progress(self, message: str, fraction: float | None) -> None:
        self.status_label.setText(message)
        if fraction is not None:
            self.progress.setValue(max(0, min(100, round(float(fraction) * 100))))

    def _on_worker_cleared(self) -> None:
        self._thread = None
        self._worker = None
        self.pages.setEnabled(True)
        self.btn_inspect.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("Fermer")
        self.btn_probe_title.setEnabled(
            self._inspection is not None and self._selected_title() is not None
        )
        self._update_start_enabled()
        self.btn_cancel.hide()
        self.btn_retry_index.setEnabled(True)
        self.btn_open_library.setEnabled(True)
        self.busy_changed.emit(False)

    def _selected_audio_indices(self) -> tuple[int, ...]:
        return tuple(
            int(self.audio_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.audio_list.count())
            if self.audio_list.item(index).checkState() == Qt.CheckState.Checked
        )

    def _update_start_enabled(self) -> None:
        if self._thread is not None or self._result_path is not None:
            self.btn_start.setEnabled(False)
            return
        ready = (
            self._inspection is not None
            and self._title_inspection is not None
            and self._selected_title() == self._title_inspection.title_index
            and self.angle_spin.value() == self._title_inspection.angle_index
            and self.destination_edit.text().strip() != ""
            and self.rights_check.isChecked()
        )
        if self.radio_audio.isChecked():
            ready = ready and bool(self._selected_audio_indices())
        if self._title_inspection is not None:
            selected = set(self._selected_audio_indices())
            pcm_required = any(
                stream.codec_name == "pcm_dvd"
                and (not self.radio_audio.isChecked() or stream.index in selected)
                for stream in self._title_inspection.audio_streams
            )
            if pcm_required:
                ready = ready and self.pcm_check.isChecked()
        self.btn_start.setEnabled(bool(ready))

    def _start_extraction(self) -> None:
        if not self.rights_check.isChecked():
            self.status_label.setText("Confirmez les droits de reproduction avant l’extraction.")
            return
        title_index = self._selected_title()
        if title_index is None or self._title_inspection is None:
            self.status_label.setText("Inspectez d’abord les pistes du titre choisi.")
            return
        destination = Path(self.destination_edit.text().strip()).expanduser()
        if not destination.is_absolute() or not destination.parent.is_dir():
            self.status_label.setText("Choisissez un chemin absolu dans un dossier existant.")
            return
        expected_suffix = ".mka" if self.radio_audio.isChecked() else ".mkv"
        if destination.suffix.casefold() != expected_suffix:
            self.status_label.setText(f"La destination doit utiliser l’extension {expected_suffix}.")
            return
        if destination.exists():
            self.status_label.setText("Le fichier existe déjà; choisissez une nouvelle destination.")
            return
        audio_indices = self._selected_audio_indices() if self.radio_audio.isChecked() else ()
        if self.radio_audio.isChecked() and not audio_indices:
            self.status_label.setText("Sélectionnez au moins une piste audio à extraire.")
            return
        pcm_required = any(
            stream.codec_name == "pcm_dvd"
            and (not self.radio_audio.isChecked() or stream.index in audio_indices)
            for stream in self._title_inspection.audio_streams
        )
        if pcm_required and not self.pcm_check.isChecked():
            self.status_label.setText("Autorisez explicitement la conversion sans perte du PCM DVD.")
            return
        operation = "audio seulement" if self.radio_audio.isChecked() else "MKV maître complet"
        confirmation = QMessageBox.question(
            self,
            "Confirmer l’extraction DVD",
            f"Confirmez-vous {operation} du titre {title_index}, angle {self.angle_spin.value()},\n"
                f"vers :\n{destination}\n\n"
                + ("Le PCM DVD 16 bits sera converti sans perte et ses échantillons vérifiés; les autres flux seront copiés."
                    if pcm_required else "Les flux seront copiés sans réencodage."),
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(
            task="audio" if self.radio_audio.isChecked() else "mkv",
            source=self.source_combo.currentText().strip(),
            destination=str(destination),
            title_index=title_index,
            angle_index=self.angle_spin.value(),
            audio_stream_indices=audio_indices,
        )

    def _cancel_or_close(self) -> None:
        if self._worker is not None:
            self.status_label.setText("Annulation demandée…")
            self.btn_cancel.setEnabled(False)
            self._worker.cancel()
            return

    def _retry_index(self) -> None:
        if self._result_path is not None:
            self.btn_retry_index.hide()
            self._start_worker(task="index", source=str(self._result_path))

    def _open_result_folder(self) -> None:
        if self._result_path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._result_path.parent)))

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._thread is not None and self._thread.isRunning():
            self._cancel_or_close()
            if not shutdown_worker_thread(self._thread, self._worker):
                event.ignore()
                return
        event.accept()