"""Wizard UI-1 : Disque → Identification → Approbation → Extraction → Terminé."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.config import AppConfig
from audio_video_manager.extraction.cd import probe_freaccmd
from audio_video_manager.extraction.cd_ripper import FreacCdRipper
from audio_video_manager.extraction.drives import CdDrive
from audio_video_manager.library.duplicates import (
    DuplicateGate,
    assess_duplicates,
    assess_from_sheet,
    format_assessment_for_user,
)
from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.logging_setup import get_logger
from audio_video_manager.metadata.approval_fingerprint import (
    compute_approval_fingerprint,
    revoke_approval,
    sync_approval_with_fingerprint,
)
from audio_video_manager.metadata.apply_lookup import (
    apply_release_candidate,
    sheet_from_disc_read,
)
from audio_video_manager.metadata.enums import ApprovalState, CoverStatus, FieldTrust, MetadataProvenance
from audio_video_manager.metadata.enrichment import (
    EnrichmentReport,
    build_enrichment_report,
)
from audio_video_manager.metadata.models import DiscMetadata, FieldMeta, TrackMetadata
from audio_video_manager.metadata.musicbrainz_client import DiscLookupResult, ReleaseCandidate
from audio_video_manager.metadata.path_preview import build_path_preview
from audio_video_manager.metadata.repository import DiscMetadataRepository
from audio_video_manager.metadata.toc_reader import (
    DiscReadResult,
    list_cdrom_device_letters,
    read_disc_toc,
    resolve_optical_device_for_discid,
)
from audio_video_manager.metadata.validation import (
    ApprovalError,
    apply_validation,
    approve_sheet,
    assert_can_start_archive_rip,
)
from audio_video_manager.orchestration.archive_job import ArchiveJobReport
from audio_video_manager.storage.database import Database
from audio_video_manager.ui.archive_worker import ArchiveWorker
from audio_video_manager.ui.cover_cache import cached_cover_path
from audio_video_manager.ui.dvd_extraction_dialog import DvdArchivePanel
from audio_video_manager.ui.identify_worker import (
    EditionEnrichmentWorker,
    IdentifyWorker,
    OpticalMediaScanWorker,
    OpticalScanResult,
)
from audio_video_manager.ui.thread_lifecycle import (
    attach_worker_thread,
    shutdown_worker_thread,
)
from audio_video_manager.ui.progress_labels import (
    PIPELINE_STEPS,
    map_progress_message,
    parse_completed_track_number,
    parse_track_number_from_progress,
    progress_step_index,
)
from audio_video_manager.ui.widgets import make_card

log = get_logger("ui.wizard")

STEP_LABELS = (
    "1 Disque",
    "2 Fiche",
    "3 Extraction",
    "4 Terminé",
)
DVD_STEP_LABELS = ("Disque", "Titres et pistes", "Options", "Extraction", "Terminé")


def _confirmed() -> FieldMeta:
    return FieldMeta(trust=FieldTrust.CONFIRMED, provenance=MetadataProvenance.MANUAL)


class ArchiveWizardPage(QWidget):
    """Session wizard conservée lors des changements de section (A3)."""

    PAGE_DISC = 0
    PAGE_REVIEW = 1
    PAGE_EXTRACT = 2
    PAGE_DONE = 3

    status_message = Signal(str)
    archive_busy_changed = Signal(bool)
    archive_status_changed = Signal(str, object, bool)
    request_navigate = Signal(int)
    library_changed = Signal()  # publication réussie → rafraîchir Bibliothèque
    open_video_library = Signal()

    def __init__(
        self,
        config: AppConfig,
        db: Database,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._db = db
        self._repo = DiscMetadataRepository(db)
        self._drives: list[CdDrive] = []
        self._disc_read: DiscReadResult | None = None
        self._sheet: DiscMetadata | None = None
        self._lookup: DiscLookupResult | None = None
        self._enrichment_report: EnrichmentReport | None = None
        self._candidates: list[ReleaseCandidate] = []
        self._selected_candidate_id: str | None = None
        self._manual_edition_choice_required = False
        self._candidate_loading = False
        self._approved_fp: str | None = None
        self._thread: QThread | None = None
        self._worker = None
        self._enrichment_jobs: dict[str, tuple[QThread, EditionEnrichmentWorker]] = {}
        self._media_scan_thread: QThread | None = None
        self._media_scan_worker: OpticalMediaScanWorker | None = None
        self._media_scan_timer = QTimer(self)
        self._media_scan_timer.setSingleShot(True)
        self._media_scan_timer.timeout.connect(self._start_optical_scan)
        self._media_scan_pending = False
        self._queued_scan_auto_identify = False
        self._queued_scan_continue = False
        self._active_scan_auto_identify = False
        self._active_scan_continue = False
        self._optical_devices: tuple[str, ...] = ()
        self._reader_pair_required = False
        self._last_report: ArchiveJobReport | None = None
        self._active_job_id: str | None = None
        self._busy = False
        self._archive_active = False
        self._completed_track_numbers: set[int] = set()
        self._last_progress_step = -1
        self._w3_loading = False
        self._advisory_warnings: list[str] = []
        self._confirmed_rearchive = False
        self._lbl_dup_w1: QLabel | None = None
        self._dvd_step = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(12)

        self._step_buttons: list[QPushButton] = []
        step_row = QHBoxLayout()
        step_row.setSpacing(8)
        for i in range(len(DVD_STEP_LABELS)):
            label = STEP_LABELS[i] if i < len(STEP_LABELS) else DVD_STEP_LABELS[i]
            # Libellés courts dans les pastilles
            short = label.split(" ", 1)[-1] if label[:1].isdigit() else label
            btn = QPushButton(short)
            btn.setVisible(i < len(STEP_LABELS))
            btn.setEnabled(False)
            btn.setFlat(True)
            btn.setProperty("step", True)
            btn.setAccessibleName(f"Étape {label}")
            self._step_buttons.append(btn)
            step_row.addWidget(btn)
        step_row.addStretch(1)
        root.addLayout(step_row)

        self._title = QLabel("Disque")
        self._title.setObjectName("wizardTitle")
        self._title.setAccessibleName("Titre de l’étape")
        self._help = QLabel("Insérez un CD audio, puis continuez.")
        self._help.setWordWrap(True)
        self._help.setObjectName("heroSub")
        root.addWidget(self._title)
        root.addWidget(self._help)

        media_row = QHBoxLayout()
        self.media_label = QLabel("Type de disque :")
        media_row.addWidget(self.media_label)
        self.media_combo = QComboBox()
        self.media_combo.setAccessibleName("Type de disque")
        self.media_combo.addItems(["CD audio", "DVD-Video"])
        media_row.addWidget(self.media_combo)
        media_row.addStretch(1)
        root.addLayout(media_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_w1())
        self._stack.addWidget(self._build_w2())
        self._stack.addWidget(self._build_w4())
        self._stack.addWidget(self._build_w5())
        self.dvd = DvdArchivePanel(config, self, db_path=db.path)
        self.dvd.busy_changed.connect(self._on_dvd_busy)
        self.dvd.extraction_finished.connect(self._on_dvd_finished)
        self.dvd.catalog_changed.connect(self.library_changed.emit)
        self.dvd.open_library_requested.connect(self.open_video_library.emit)
        self.dvd.finalize_existing_requested.connect(self._finalize_existing_video)
        self._stack.addWidget(self.dvd)
        self.media_combo.currentIndexChanged.connect(self._on_media_changed)
        root.addWidget(self._stack, 1)

        nav = QHBoxLayout()
        self.btn_back = QPushButton("← Retour")
        self.btn_back.setAccessibleName("Retour à l’étape précédente")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_next = QPushButton("Continuer →")
        self.btn_next.setProperty("primary", True)
        self.btn_next.setAccessibleName("Continuer vers l’étape suivante")
        self.btn_next.clicked.connect(self._go_next)
        nav.addWidget(self.btn_back)
        nav.addStretch(1)
        nav.addWidget(self.btn_next)
        root.addLayout(nav)

        self._set_step(0)
        if self._automatic_optical_detection_enabled():
            self.schedule_optical_scan(auto_identify=True)
        else:
            self.refresh_drives()

    # --- public ---
    def set_config(self, config: AppConfig) -> None:
        self._config = config
        if hasattr(self, "lbl_destination"):
            self.lbl_destination.setText(config.library_root)
        self.dvd.set_config(config)
        if self._automatic_optical_detection_enabled():
            self.schedule_optical_scan()
        else:
            self.refresh_drives()

    def is_busy(self) -> bool:
        return self._busy or self._media_scan_thread is not None

    def is_archive_active(self) -> bool:
        return self._archive_active

    def available_drives(self) -> list[CdDrive]:
        return list(self._drives)

    def is_media_scan_busy(self) -> bool:
        return self._media_scan_thread is not None

    def current_step(self) -> int:
        return self._dvd_step if self.media_combo.currentIndex() == 1 else self._stack.currentIndex()

    def approval_fingerprint(self) -> str | None:
        return self._approved_fp

    def sheet(self) -> DiscMetadata | None:
        return self._sheet

    @staticmethod
    def _automatic_optical_detection_enabled() -> bool:
        app = QApplication.instance()
        return bool(
            os.name == "nt"
            and app is not None
            and app.platformName().casefold() != "offscreen"
        )

    def _populate_freac_drives(self, drives: tuple[CdDrive, ...] | list[CdDrive]) -> None:
        previous = self.combo_drives.currentData()
        self.combo_drives.blockSignals(True)
        self.combo_drives.clear()
        self._drives = list(drives)
        letter = self._optical_devices[0] if len(self._optical_devices) == 1 else None
        for drive in self._drives:
            label = drive.friendly_label(letter)
            if len(self._drives) > 1:
                label += f" — {drive.designation}"
            self.combo_drives.addItem(label, drive.number)
            index = self.combo_drives.count() - 1
            self.combo_drives.setItemData(index, drive.label(), Qt.ItemDataRole.ToolTipRole)
        index = self.combo_drives.findData(previous)
        if index < 0:
            index = next(
                (i for i, drive in enumerate(self._drives)
                 if drive.number == self._config.last_drive_number),
                0 if self._drives else -1,
            )
        self.combo_drives.setCurrentIndex(index)
        self.combo_drives.blockSignals(False)

    def _populate_optical_devices(self, devices: tuple[str, ...]) -> None:
        previous = self.combo_optical_devices.currentData()
        self.combo_optical_devices.blockSignals(True)
        self.combo_optical_devices.clear()
        self._optical_devices = devices
        for device in devices:
            self.combo_optical_devices.addItem(
                f"Lecteur Windows ({device})", device
            )
        index = self.combo_optical_devices.findData(previous)
        if index < 0 and len(devices) == 1:
            index = 0
        elif index < 0 and len(devices) != 1:
            index = -1
        self.combo_optical_devices.setCurrentIndex(index)
        self.combo_optical_devices.blockSignals(False)

    def schedule_optical_scan(
        self,
        *,
        auto_identify: bool = False,
        continue_after: bool = False,
        manual: bool = False,
    ) -> None:
        if self.media_combo.currentIndex() != 0:
            return
        if self._stack.currentIndex() >= self.PAGE_DONE or self._busy:
            return
        if not manual and not self._automatic_optical_detection_enabled():
            return
        self._queued_scan_auto_identify |= auto_identify
        self._queued_scan_continue |= continue_after
        if self._media_scan_thread is not None:
            self._media_scan_pending = True
            return
        self._media_scan_timer.start(300)

    def _manual_optical_refresh(self) -> None:
        self.schedule_optical_scan(manual=True)

    def _on_toc_device_selected(self, _index: int) -> None:
        selected = self.combo_optical_devices.currentData()
        if self._disc_read is not None and selected != self._disc_read.device:
            self._disc_read = None
            if self._sheet is not None and self._sheet.approval == ApprovalState.APPROVED:
                revoke_approval(
                    self._sheet,
                    note="Le lecteur Windows TOC a changé. Relisez le disque et approuvez à nouveau.",
                )
                self._approved_fp = None
            self.lbl_disc.setText(
                "Lecteur Windows modifié. Cliquez sur « Relire le disque » pour vérifier la TOC."
            )
        if hasattr(self, "chk_reader_pair"):
            self.chk_reader_pair.setChecked(False)

    def _start_optical_scan(self) -> None:
        if (
            self.media_combo.currentIndex() != 0
            or self._stack.currentIndex() >= self.PAGE_DONE
            or self._busy
        ):
            self._queued_scan_auto_identify = False
            self._queued_scan_continue = False
            return
        if self._media_scan_thread is not None:
            self._media_scan_pending = True
            return
        self._active_scan_auto_identify = self._queued_scan_auto_identify
        self._active_scan_continue = self._queued_scan_continue
        self._queued_scan_auto_identify = False
        self._queued_scan_continue = False
        self.btn_refresh_drives.setEnabled(False)
        self.btn_reread.setEnabled(False)
        self.btn_next.setEnabled(False)
        worker = OpticalMediaScanWorker(self._config)
        thread = attach_worker_thread(
            worker,
            on_finished=self._on_optical_scan_finished,
            on_failed=self._on_optical_scan_failed,
            on_cleared=self._on_optical_scan_cleared,
        )
        self._media_scan_worker = worker
        self._media_scan_thread = thread
        thread.start()

    def _on_optical_scan_finished(self, result: object) -> None:
        if (
            self.media_combo.currentIndex() != 0
            or self._stack.currentIndex() >= self.PAGE_DONE
        ):
            return
        if not isinstance(result, OpticalScanResult):
            self._on_optical_scan_failed("Résultat de détection invalide.")
            return
        self._populate_freac_drives(result.drives)
        self._populate_optical_devices(result.devices)
        self._reader_pair_required = len(result.drives) > 1 or len(result.devices) > 1
        self.chk_reader_pair.setVisible(self._reader_pair_required)
        self.chk_reader_pair.setChecked(False)
        self.lbl_reader_mapping.setVisible(self._reader_pair_required)

        selected_device = self.combo_optical_devices.currentData()
        detected = list(result.discs)
        selected = next(
            (disc for disc in detected if disc.device == selected_device), None
        )
        if selected is None and len(detected) == 1:
            selected = detected[0]
            index = self.combo_optical_devices.findData(selected.device)
            if index >= 0:
                self.combo_optical_devices.blockSignals(True)
                self.combo_optical_devices.setCurrentIndex(index)
                self.combo_optical_devices.blockSignals(False)
        if selected is None and len(detected) > 1:
            if self._disc_read is not None:
                previous = next(
                    (
                        disc
                        for disc in detected
                        if disc.device == self._disc_read.device
                        and disc.disc_id == self._disc_read.disc_id
                    ),
                    None,
                )
                if previous is not None:
                    selected = previous
            if selected is None and self._disc_read is not None:
                self._handle_optical_media_removed()
        if selected is None and len(detected) > 1:
            self.lbl_disc.setText(
                "Plusieurs CD audio sont détectés. Choisissez le lecteur Windows à lire, "
                "puis cliquez sur « Relire le disque »."
            )
            return
        if selected is not None:
            changed = self._accept_disc_read(selected)
            needs_identification = self._active_scan_continue or (
                self._active_scan_auto_identify
                and (changed or self._sheet is None)
            )
            if needs_identification and not self._busy:
                if self._stack.currentIndex() != 1:
                    self._set_step(1)
                self._start_identify()
            return

        if self._disc_read is not None:
            self._handle_optical_media_removed()
        if not result.devices:
            message = "Aucun lecteur optique Windows détecté. Vous pouvez choisir un lecteur fre:ac puis actualiser."
        else:
            message = "Aucun CD audio lisible détecté. Insérez un CD audio ou choisissez un lecteur puis actualisez."
            if result.read_errors:
                message += f"\n{result.read_errors[0]}"
        if not result.drives and result.freaccmd_error:
            message += f"\nfreaccmd : {result.freaccmd_error}"
        self.lbl_disc.setText(message)

    def _accept_disc_read(self, result: DiscReadResult) -> bool:
        previous = self._disc_read
        previous_disc_id = (
            self._sheet.identity.disc_id
            if self._sheet is not None
            else previous.disc_id if previous is not None else None
        )
        changed = bool(previous_disc_id and previous_disc_id != result.disc_id)
        self._disc_read = result
        mins = sum(result.toc.track_durations_ms) // 60000
        self.lbl_disc.setText(
            f"CD détecté dans {result.device} — {result.toc.audio_track_count} pistes · environ {mins} minutes"
        )
        self.lbl_disc_details.setText(f"Disc ID : {result.disc_id}")
        self.lbl_disc_details.setToolTip(result.disc_id or "")
        self.lbl_disc_details.setVisible(self.btn_tech_details.isChecked())
        self._confirmed_rearchive = False
        self._advise_duplicates_on_disc_read(
            result.disc_id, result.toc.audio_track_count
        )
        if changed and not self._archive_active:
            if self._sheet is not None and self._sheet.approval == ApprovalState.APPROVED:
                revoke_approval(
                    self._sheet,
                    note="Le disque a changé. Approuvez à nouveau avant d’extraire.",
                )
            self._approved_fp = None
            self._sheet = None
            self._lookup = None
            self._candidates = []
            self._enrichment_report = None
            self._last_report = None
            self._active_job_id = None
            self._reset_archive_tracking()
            if self._stack.currentIndex() == self.PAGE_DONE:
                self._set_step(self.PAGE_DISC)
        self.status_message.emit(
            f"CD {result.toc.audio_track_count} pistes · environ {mins} min"
        )
        return changed

    def _handle_optical_media_removed(self) -> None:
        self._disc_read = None
        if self._sheet is not None and self._sheet.approval == ApprovalState.APPROVED:
            revoke_approval(
                self._sheet,
                note="Le CD a été retiré. Relisez le disque et approuvez à nouveau.",
            )
            self._approved_fp = None
        if self._stack.currentIndex() == 0:
            self._reset_session()
        else:
            self.lbl_id_warn.setText(
                "Le CD a été retiré ou n’est plus lisible. Relisez le disque avant l’extraction."
            )
        self.lbl_disc.setText(
            "CD retiré ou non lisible. Insérez un CD audio puis utilisez « Actualiser les lecteurs » ou « Relire le disque »."
        )

    def _on_optical_scan_failed(self, message: str) -> None:
        self.lbl_disc.setText(f"Détection du CD impossible : {message}. Vous pouvez actualiser ou choisir un lecteur.")

    def _on_optical_scan_cleared(self) -> None:
        self._media_scan_thread = None
        self._media_scan_worker = None
        self.btn_refresh_drives.setEnabled(True)
        self.btn_reread.setEnabled(True)
        self.btn_next.setEnabled(not self._busy)
        if self._media_scan_pending:
            self._media_scan_pending = False
            self._media_scan_timer.start(0)

    def refresh_drives(self) -> None:
        st = probe_freaccmd(
            configured_path=self._config.freaccmd_path or None,
            freac_install_dir=self._config.freac_install_dir or None,
            run_probes=False,
        )
        if not st.found or not st.path:
            self._populate_freac_drives(())
            self.lbl_disc.setText(
                "L’outil d’extraction est introuvable. "
                "Ouvrez Paramètres pour indiquer son emplacement."
            )
            return
        try:
            drives = FreacCdRipper(st.path).list_drives()
        except OSError as exc:
            self._populate_freac_drives(())
            self.lbl_disc.setText(f"Lecteurs indisponibles : {exc}")
            return
        self._populate_freac_drives(drives)

    # --- step chrome ---
    def _set_step(self, index: int) -> None:
        if self.media_combo.currentIndex() == 1:
            self._set_dvd_step(index)
            return
        self._stack.setCurrentIndex(index)
        self.media_combo.setVisible(index == self.PAGE_DISC)
        self.media_label.setVisible(index == self.PAGE_DISC)
        titles = [
            ("Disque", "Confirmez le lecteur et le CD à archiver."),
            (
                "Identifier et vérifier",
                "En continuant, vous approuvez cette fiche. L’extraction ne démarre qu’après votre action « Extraire ».",
            ),
            ("Extraction", "Vérifiez la destination. Le CD doit rester le même jusqu’à la fin."),
            ("Terminé", "Résultat de l’archivage."),
        ]
        self._title.setText(titles[index][0])
        self._help.setText(titles[index][1])
        for i, btn in enumerate(self._step_buttons):
            if i >= len(STEP_LABELS):
                btn.hide()
                continue
            btn.show()
            btn.setText(STEP_LABELS[i].split(" ", 1)[-1])
            btn.setAccessibleName(f"Étape {STEP_LABELS[i]}")
            btn.setEnabled(False)
            btn.setProperty("active", "true" if i == index else "false")
            btn.setProperty("done", "true" if i < index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.btn_back.setEnabled(
            index > self.PAGE_DISC and index < self.PAGE_DONE and not self._busy
        )
        if index == self.PAGE_DONE:
            self.btn_next.setText("Archiver un autre CD")
            self.btn_next.setAccessibleName("Archiver un autre CD")
            self.btn_next.setEnabled(True)
        elif index == self.PAGE_EXTRACT:
            self.btn_next.setText("Extraire")
            self.btn_next.setAccessibleName("Extraire et publier l’album")
            self.btn_next.setEnabled(not self._busy)
            self._refresh_w4_preview()
        elif index == self.PAGE_REVIEW:
            self.btn_next.setText("Continuer")
            self.btn_next.setAccessibleName("Continuer et approuver la fiche")
            self.btn_next.setEnabled(not self._busy)
            self._refresh_w3()
        else:
            self.btn_next.setText("Continuer")
            self.btn_next.setAccessibleName("Continuer vers l’étape suivante")
            self.btn_next.setEnabled(not self._busy)

    def _on_media_changed(self, _index: int) -> None:
        if _index == 1:
            self._media_scan_timer.stop()
            self._media_scan_pending = False
            self._queued_scan_auto_identify = False
            self._queued_scan_continue = False
            if self._media_scan_worker is not None:
                self._media_scan_worker.cancel()
        self._set_step(0)
        if _index == 0:
            self.schedule_optical_scan(auto_identify=True)

    def _set_dvd_step(self, index: int) -> None:
        self._dvd_step = index
        self._stack.setCurrentWidget(self.dvd)
        self.media_combo.setVisible(index == 0)
        self.media_label.setVisible(index == 0)
        for btn in self._step_buttons:
            btn.show()
        self.dvd.set_step(index)
        titles = (
            ("Disque", "Choisissez et inspectez la source DVD-Video."),
            ("Titres et pistes", "Choisissez le titre et l’angle, puis vérifiez les pistes."),
            ("Options", "Choisissez le format et la destination, puis confirmez vos droits."),
            ("Extraire", "Confirmez l’extraction et suivez sa progression."),
            ("Terminé", "Résultat de l’extraction DVD."),
        )
        self._title.setText(titles[index][0])
        self._help.setText(titles[index][1])
        for position, btn in enumerate(self._step_buttons):
            btn.setText(DVD_STEP_LABELS[position])
            btn.setAccessibleName(f"Étape {position + 1} {DVD_STEP_LABELS[position]}")
            btn.setProperty("active", "true" if position == index else "false")
            btn.setProperty("done", "true" if position < index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.btn_back.setEnabled(0 < index < 4 and not self._busy)
        self.btn_next.setEnabled(not self._busy)
        self.btn_next.setText(
            "Archiver un autre disque" if index == 4 else
            "Lancer l’extraction" if index == 3 else
            "Inspecter le disque" if index == 0 and self.dvd._inspection is None else "Continuer →"
        )
        self.btn_next.setAccessibleName(self.btn_next.text())

    def _on_dvd_busy(self, busy: bool) -> None:
        self._busy = busy
        self.media_combo.setEnabled(not busy)
        self.archive_busy_changed.emit(busy)
        self._set_dvd_step(self._dvd_step)

    def _on_dvd_finished(self) -> None:
        self._set_dvd_step(4)

    def _finalize_existing_video(self) -> None:
        if self._busy:
            return
        source, _ = QFileDialog.getOpenFileName(self, "Choisir un MKV existant", "", "Vidéo Matroska (*.mkv)")
        if not source:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self, "Destination de la vidéo", str(Path(self._config.library_root) / Path(source).name),
            "Vidéo Matroska (*.mkv)",
        )
        if not destination:
            return
        if QMessageBox.question(
            self, "Confirmer la finalisation",
            f"Copier et valider :\n{source}\n\nVers :\n{destination}\n\n"
            "La source restera intacte. La lecture sera vérifiée, mais pas la fidélité au DVD.",
        ) != QMessageBox.StandardButton.Yes:
            return
        from audio_video_manager.ui.video_worker import VideoFinalizeWorker

        worker = VideoFinalizeWorker(self._db.path, source, destination, self._config.ffmpeg_path)
        self._worker = worker
        self.dvd.pages.setEnabled(False)
        self.dvd.status_label.setText("Copie et vérification de la vidéo en cours…")
        self._on_dvd_busy(True)
        self._thread = attach_worker_thread(
            worker, on_finished=self._on_video_finalized,
            on_failed=self._on_video_finalize_failed, on_cleared=self._on_video_finalize_cleared,
        )
        self._thread.start()

    def _on_video_finalized(self, destination: object) -> None:
        self.dvd._result_path = Path(str(destination))
        self.dvd._cataloged = True
        self.dvd.btn_open_result.setEnabled(True)
        self.dvd.progress.setValue(100)
        self.dvd.status_label.setText(
            f"Vidéo décodable publiée : {destination}\nFidélité à la source DVD non vérifiée."
        )
        self.library_changed.emit()
        self._set_dvd_step(4)

    def _on_video_finalize_failed(self, message: str) -> None:
        self.dvd.status_label.setText(f"Finalisation non terminée : {message}")
        self.library_changed.emit()

    def _on_video_finalize_cleared(self) -> None:
        self._clear_thread()
        self.dvd.pages.setEnabled(True)
        self._on_dvd_busy(False)

    def _go_back(self) -> None:
        if self._busy:
            return
        if self.media_combo.currentIndex() == 1:
            if self._dvd_step > 0:
                self._set_dvd_step(self._dvd_step - 1)
            return
        cur = self._stack.currentIndex()
        if cur <= self.PAGE_DISC:
            return
        # A3 : retour sans edit conserve Approved
        self._set_step(cur - 1)

    def _go_next(self) -> None:
        if self.media_combo.currentIndex() == 1:
            self._go_next_dvd()
            return
        if self._busy and self._stack.currentIndex() != self.PAGE_DONE:
            return
        cur = self._stack.currentIndex()
        if cur == self.PAGE_DISC:
            self._read_toc_and_continue()
        elif cur == self.PAGE_REVIEW:
            if self._sheet is None:
                QMessageBox.information(self, "Identification", "Identifiez d’abord le disque.")
                return
            if not self._do_approve():
                return
            self._set_step(self.PAGE_EXTRACT)
        elif cur == self.PAGE_EXTRACT:
            self._start_archive()
        elif cur == self.PAGE_DONE:
            self._reset_session()
            self._set_step(self.PAGE_DISC)

    def _go_next_dvd(self) -> None:
        if self._busy:
            return
        if self._dvd_step == 0 and self.dvd._inspection is None:
            self.dvd._inspect()
        elif self._dvd_step == 1 and self.dvd._title_inspection is None:
            self.dvd._inspect_selected_title()
        elif self._dvd_step == 2 and not self.dvd.btn_start.isEnabled():
            self.dvd.status_label.setText("Choisissez la destination, les pistes audio et confirmez vos droits.")
        elif self._dvd_step < 3:
            self._set_dvd_step(self._dvd_step + 1)
            if self._dvd_step == 1 and self.dvd._title_inspection is None:
                self.dvd._inspect_selected_title()
        elif self._dvd_step == 3:
            self.dvd._start_extraction()
        else:
            self.dvd._result_path = None
            self.dvd._cataloged = False
            self.dvd.btn_open_result.setEnabled(False)
            self.dvd.btn_retry_index.hide()
            self.dvd._invalidate_inspection()
            self.dvd.progress.setValue(0)
            self.dvd.rights_check.setChecked(False)
            self._set_dvd_step(0)

    # --- W1 ---
    def _build_w1(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(12)
        form = QFormLayout()
        self.combo_drives = QComboBox()
        self.combo_drives.setMaximumWidth(420)
        self.combo_drives.setAccessibleName("Lecteur fre:ac à utiliser pour l’extraction")
        self.combo_drives.currentIndexChanged.connect(self._on_freac_drive_selected)
        form.addRow("Lecteur fre:ac :", self.combo_drives)
        self.combo_optical_devices = QComboBox()
        self.combo_optical_devices.setAccessibleName("Lecteur Windows utilisé pour lire la TOC")
        self.combo_optical_devices.currentIndexChanged.connect(
            self._on_toc_device_selected
        )
        form.addRow("Lecteur Windows (TOC) :", self.combo_optical_devices)
        v.addLayout(form)
        self.lbl_disc = QLabel("Insérez un CD audio, puis cliquez sur Relire le disque.")
        self.lbl_disc.setWordWrap(True)
        v.addWidget(self.lbl_disc)
        self.lbl_reader_mapping = QLabel(
            "Lecteur fre:ac = extraction; lecteur Windows = lecture de la TOC. "
            "Si plusieurs lecteurs sont présents, sélectionnez le même lecteur dans les deux listes."
        )
        self.lbl_reader_mapping.setWordWrap(True)
        self.lbl_reader_mapping.setProperty("role", "muted")
        self.lbl_reader_mapping.hide()
        v.addWidget(self.lbl_reader_mapping)
        # Disc ID replié — hors parcours normal (AVM-06O)
        self.btn_tech_details = QPushButton("Détails techniques…")
        self.btn_tech_details.setProperty("ghost", True)
        self.btn_tech_details.setCheckable(True)
        self.btn_tech_details.setChecked(False)
        self.btn_tech_details.setMaximumWidth(200)
        self.btn_tech_details.setAccessibleName("Afficher les détails techniques du disque")
        self.btn_tech_details.toggled.connect(self._toggle_tech_details)
        v.addWidget(self.btn_tech_details, alignment=Qt.AlignmentFlag.AlignLeft)
        self.lbl_disc_details = QLabel("")
        self.lbl_disc_details.setWordWrap(True)
        self.lbl_disc_details.setProperty("role", "muted")
        self.lbl_disc_details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.lbl_disc_details.hide()
        v.addWidget(self.lbl_disc_details)
        self._lbl_dup_w1 = QLabel("")
        self._lbl_dup_w1.setWordWrap(True)
        self._lbl_dup_w1.setProperty("role", "muted")
        self._lbl_dup_w1.setAccessibleName("Avertissement doublon disque")
        v.addWidget(self._lbl_dup_w1)
        actions = QHBoxLayout()
        self.btn_refresh_drives = QPushButton("Actualiser les lecteurs")
        self.btn_refresh_drives.setAccessibleName("Actualiser les lecteurs et rechercher un CD audio")
        self.btn_refresh_drives.clicked.connect(self._manual_optical_refresh)
        actions.addWidget(self.btn_refresh_drives)
        self.btn_reread = QPushButton("Relire le disque")
        self.btn_reread.setProperty("primary", True)
        self.btn_reread.setMaximumWidth(280)
        self.btn_reread.setAccessibleName("Relire le disque")
        self.btn_reread.clicked.connect(self._on_reread)
        actions.addWidget(self.btn_reread)
        actions.addStretch(1)
        v.addLayout(actions)
        v.addStretch(1)
        return w

    def _toggle_tech_details(self, checked: bool) -> None:
        self.lbl_disc_details.setVisible(checked and bool(self.lbl_disc_details.text()))
        self.btn_tech_details.setText(
            "Masquer les détails techniques" if checked else "Détails techniques…"
        )

    def _optical_device(self) -> str | None:
        index = self.combo_drives.currentIndex()
        if 0 <= index < len(self._drives):
            self._config.last_drive_number = self._drives[index].number
        device = self.combo_optical_devices.currentData()
        if device:
            return str(device)
        # Preserve the non-Windows default-device fallback for manual use.
        if os.name != "nt":
            device, reason = resolve_optical_device_for_discid(
                self._drives[index].designation if 0 <= index < len(self._drives) else None
            )
            log.info("optical: %s (%s)", device, reason)
            return device
        return None

    def _on_reread(self) -> None:
        self.schedule_optical_scan(manual=True)

    def _read_toc_and_continue(self) -> None:
        selected_device = self._optical_device()
        if self._disc_read is not None and (
            selected_device is None or self._disc_read.device == selected_device
        ):
            self._set_step(1)
            self._start_identify()
            return
        self.schedule_optical_scan(auto_identify=True, continue_after=True, manual=True)

    def _on_freac_drive_selected(self, _index: int) -> None:
        if hasattr(self, "chk_reader_pair"):
            self.chk_reader_pair.setChecked(False)

    def _manual_optical_refresh(self) -> None:
        self.schedule_optical_scan(manual=True)

    # --- W2 ---
    def _build_w2(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("archiveReviewScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        v = QVBoxLayout(content)
        v.setContentsMargins(12, 8, 12, 12)
        v.setSpacing(10)
        review_fields = self._build_w3()
        top = QHBoxLayout()
        self.cover_label = QLabel()
        self.cover_label.setObjectName("coverPlaceholder")
        self.cover_label.setFixedSize(128, 128)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setWordWrap(True)
        self.cover_label.setAccessibleName("Pochette album")
        self.cover_label.setText("—")
        top.addWidget(self.cover_label)
        meta = QVBoxLayout()
        album_fields = QFormLayout()
        album_fields.setHorizontalSpacing(10)
        album_fields.setVerticalSpacing(6)
        album_fields.addRow("Album *", self.edit_album)
        album_fields.addRow("Artiste *", self.edit_artist)
        album_fields.addRow("Année", self._year_row)
        album_fields.addRow("Type", self.chk_compilation)
        meta.addLayout(album_fields)
        self.lbl_id_warn = QLabel("")
        self.lbl_id_warn.setWordWrap(True)
        self.lbl_id_warn.setProperty("role", "warning")
        meta.addWidget(self.lbl_id_warn)
        edition_row = QHBoxLayout()
        edition_label = QLabel("Édition")
        self.combo_editions = QComboBox()
        self.combo_editions.setAccessibleName("Édition MusicBrainz")
        self.combo_editions.setToolTip("Le choix met à jour immédiatement la fiche ci-dessous.")
        self.combo_editions.currentIndexChanged.connect(self._on_edition_selected)
        self.combo_editions.activated.connect(self._on_edition_activated)
        self.combo_editions.activated.connect(self._on_edition_activated)
        edition_row.addWidget(edition_label)
        edition_row.addWidget(self.combo_editions, 1)
        meta.addLayout(edition_row)
        top.addLayout(meta, 1)
        v.addLayout(top)
        self.lbl_id_status = QLabel("")
        self.lbl_id_status.setWordWrap(True)
        self.lbl_id_status.setProperty("role", "muted")
        v.addWidget(self.lbl_id_status)
        v.addWidget(review_fields)
        v.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page

    def _start_identify(self) -> None:
        self._manual_edition_choice_required = False
        self.lbl_id_status.setText("Recherche des informations…")
        self.combo_editions.clear()
        self._set_busy(True)
        worker = IdentifyWorker(
            optical_device=self._optical_device(),
            preferred_country=self._config.preferred_release_country or "CA",
            disc_read=self._disc_read,
        )
        thread = attach_worker_thread(
            worker,
            on_finished=self._on_identify_ok,
            on_failed=self._on_identify_fail,
            on_cleared=self._clear_thread,
        )
        self._thread = thread
        self._worker = worker
        thread.start()

    def _on_identify_fail(self, message: str) -> None:
        self._set_busy(False)
        self._manual_edition_choice_required = False
        if self._disc_read is not None:
            if self._approved_fp:
                self._approved_fp = None
            self._sheet = sheet_from_disc_read(self._disc_read)
            self._lookup = None
            self._enrichment_report = None
            self._candidates = []
            self._selected_candidate_id = None
            self._fill_identify_ui(None, None)
            self._refresh_w3()
        self.lbl_id_status.setText(
            "Recherche en ligne indisponible. Vous pourrez compléter la fiche manuellement ci-dessous."
        )
        self.lbl_id_status.setToolTip(message)

    def _on_identify_ok(self, sheet, lookup, cover, decision, enrichment) -> None:
        self._set_busy(False)
        # A3 : nouvelle identification = nouvelles données → révoque l’empreinte
        if self._approved_fp:
            self._approved_fp = None
            if isinstance(sheet, DiscMetadata) and sheet.approval == ApprovalState.APPROVED:
                revoke_approval(
                    sheet,
                    note="Nouvelle identification — réapprobation requise.",
                )
        self._sheet = sheet
        self._lookup = lookup
        self._enrichment_report = enrichment
        self._candidates = list(lookup.candidates) if lookup else []
        usable_release_count = sum(
            not candidate.is_cdstub for candidate in self._candidates
        )
        self._manual_edition_choice_required = bool(
            decision is not None
            and getattr(decision, "require_manual_choice", False)
            and getattr(decision, "selected", None) is not None
            and usable_release_count > 1
        )
        self._selected_candidate_id = getattr(getattr(decision, "selected", None), "selection_key", None)
        log.info(
            "AVM28E_TRACE worker_delivered disc_id=%s candidates=%d selected=%s "
            "album=%r artist=%r year=%s tracks=%d",
            sheet.identity.disc_id,
            len(self._candidates),
            self._selected_candidate_id,
            sheet.edition.album_title,
            sheet.edition.album_artist,
            sheet.edition.year,
            len(sheet.tracks),
        )
        self._fill_identify_ui(cover, decision)
        self._refresh_w3()
        log.info(
            "AVM28E_TRACE widgets_refreshed source=identify selected=%s "
            "album=%r artist=%r year=%s tracks=%d path_rows=%d",
            self.combo_editions.currentData(),
            self.edit_album.text(),
            self.edit_artist.text(),
            self.spin_year.value() or None,
            self.table.rowCount(),
            len(self.lbl_path_preview.text().splitlines()),
        )
        if (
            decision is not None
            and getattr(decision, "selected", None) is not None
        ):
            self._start_edition_enrichment(decision.selected)
        ok, msg = sync_approval_with_fingerprint(self._sheet, self._approved_fp)
        if not ok and msg:
            self._approved_fp = None
            self.lbl_id_warn.setText(msg)
            self.lbl_id_warn.setVisible(True)

    def _fill_identify_ui(self, cover, decision) -> None:
        assert self._sheet is not None
        ed = self._sheet.edition
        warns = list(self._sheet.validation_warnings)
        if decision is not None and getattr(decision, "warnings", None):
            warns.extend(decision.warnings)
        # Conservés hors sheet.validation_warnings (écrasés par apply_validation en W3)
        seen: set[str] = set()
        self._advisory_warnings = []
        for w in warns:
            if w and w not in seen:
                seen.add(w)
                self._advisory_warnings.append(w)
        self.lbl_id_warn.setText("\n".join(f"• {w}" for w in self._advisory_warnings[:6]))
        self.lbl_id_warn.setVisible(bool(self._advisory_warnings))
        self._selected_candidate_id = (
            getattr(getattr(decision, "selected", None), "selection_key", None)
            or self._selected_candidate_id
        )
        self._candidate_loading = True
        self.combo_editions.blockSignals(True)
        self.combo_editions.clear()
        for c in self._candidates:
            track_count = c.medium_track_count or len(c.track_titles)
            details = " · ".join(
                part for part in (
                    c.country,
                    str(c.year) if c.year else None,
                    f"{track_count} pistes" if track_count else None,
                    c.catalog_numbers[0] if c.catalog_numbers else None,
                    "TOC" if c.match_source == "toc" else None,
                    "CD stub non confirmé" if c.is_cdstub else None,
                ) if part
            )
            label = " — ".join(
                value for value in (c.artist_credit, c.title) if value
            ) or "Résultat MusicBrainz sans titre ni artiste"
            self.combo_editions.addItem(
                f"{label} ({details})" if details else label,
                c.selection_key,
            )
            self.combo_editions.setItemData(
                self.combo_editions.count() - 1,
                c.disambiguation or c.selection_key,
                Qt.ItemDataRole.ToolTipRole,
            )
        selected_index = self.combo_editions.findData(self._selected_candidate_id)
        self.combo_editions.setCurrentIndex(selected_index)
        self.combo_editions.setEnabled(bool(self._candidates))
        self.combo_editions.setVisible(bool(self._candidates))
        self.combo_editions.blockSignals(False)
        self._candidate_loading = False
        selected_candidate = next(
            (
                candidate
                for candidate in self._candidates
                if candidate.selection_key == self._selected_candidate_id
            ),
            None,
        )
        if selected_candidate is not None and selected_candidate.is_cdstub:
            self.lbl_id_status.setText(
                "Métadonnées préremplies depuis un CD stub; ce résultat ne confirme pas une édition. "
                "L’année ou la pochette reste absente si MusicBrainz ne les fournit pas."
            )
        elif self._manual_edition_choice_required:
            if self._selected_candidate_id:
                self.lbl_id_status.setText(
                    f"{sum(not candidate.is_cdstub for candidate in self._candidates)} éditions proposées. "
                    "Proposition présélectionnée, pas encore confirmée. "
                    "Choisissez explicitement l’édition dans la liste avant de continuer."
                )
            else:
                self.lbl_id_status.setText(
                    "Aucune édition ne correspond clairement à la TOC. Consultez les résultats avant de continuer."
                )
        elif not self._candidates:
            self.lbl_id_status.setText(
                "Aucune édition trouvée pour le Disc ID ou la TOC; la fiche n’a pas été complétée."
            )
        elif selected_candidate is not None and selected_candidate.match_source == "toc":
            self.lbl_id_status.setText(
                "Édition unique trouvée par la TOC. Vérifiez la fiche, puis continuez pour l’approuver."
            )
        else:
            self.lbl_id_status.setText("")
        url = None
        if cover is not None and getattr(cover, "thumbnail_url", None):
            url = cover.thumbnail_url or cover.front_url
        elif ed.cover_path_or_url and str(ed.cover_path_or_url).startswith("http"):
            url = ed.cover_path_or_url
        self._load_cover(url)

    def _load_cover(self, url: str | None) -> bool:
        self.cover_label.setPixmap(QPixmap())
        self.cover_label.setText("—")
        if not url:
            return False
        path = cached_cover_path(url)
        if path and path.is_file():
            return self._show_cover_path(path)
        return False

    def _show_cover_path(self, path: Path) -> bool:
        pix = QPixmap(str(path))
        if pix.isNull():
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("—")
            return False
        self.cover_label.setPixmap(
            pix.scaled(
                144,
                144,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.cover_label.setText("")
        return True

    def _candidate_manual_overrides(self, candidate: ReleaseCandidate):
        if self._sheet is None:
            return []
        overrides = []
        edition_values = (
            ("album_title", candidate.title, "titre de l’album"),
            ("album_artist", candidate.artist_credit, "artiste de l’album"),
            ("year", candidate.year, "année"),
            ("first_release_date", candidate.release_group_first_release_date, "date de première sortie"),
            ("country", candidate.country, "pays"),
            ("label", candidate.labels[0] if candidate.labels else None, "label"),
            ("catalog_number", candidate.catalog_numbers[0] if candidate.catalog_numbers else None, "numéro de catalogue"),
        )
        for key, value, label in edition_values:
            meta = self._sheet.edition.field_meta.get(key)
            if (
                value not in (None, "")
                and getattr(self._sheet.edition, key) != value
                and meta is not None
                and meta.trust == FieldTrust.CONFIRMED
                and meta.provenance in (MetadataProvenance.MANUAL, MetadataProvenance.USER_CORRECTION)
            ):
                overrides.append((self._sheet.edition.field_meta, key, label))
        disc_values = (
            ("disc_number", candidate.matched_medium_position, "numéro du disque"),
            ("disc_total", candidate.medium_count, "nombre de disques"),
        )
        for key, value, label in disc_values:
            meta = self._sheet.disc.field_meta.get(key)
            if (
                value is not None
                and getattr(self._sheet.disc, key) != value
                and meta is not None
                and meta.trust == FieldTrust.CONFIRMED
                and meta.provenance in (MetadataProvenance.MANUAL, MetadataProvenance.USER_CORRECTION)
            ):
                overrides.append((self._sheet.disc.field_meta, key, label))
        for index, track in enumerate(self._sheet.tracks):
            for key, values, label in (
                ("title", candidate.track_titles, f"titre de la piste {track.number}"),
                ("artist", candidate.track_artists, f"artiste de la piste {track.number}"),
            ):
                value = values[index] if index < len(values) else None
                meta = track.field_meta.get(key)
                if (
                    value not in (None, "")
                    and getattr(track, key) != value
                    and meta is not None
                    and meta.trust == FieldTrust.CONFIRMED
                    and meta.provenance in (MetadataProvenance.MANUAL, MetadataProvenance.USER_CORRECTION)
                ):
                    overrides.append((track.field_meta, key, label))
        return overrides

    def _on_edition_selected(self, index: int) -> None:
        if self._candidate_loading or not self._sheet or index < 0:
            return
        selection_key = self.combo_editions.itemData(index)
        candidate = next(
            (item for item in self._candidates if item.selection_key == selection_key),
            None,
        )
        if candidate is None:
            return
        if candidate.selection_key == self._selected_candidate_id:
            if self._manual_edition_choice_required:
                self._manual_edition_choice_required = False
                apply_release_candidate(
                    self._sheet,
                    candidate,
                    user_selected=not candidate.is_cdstub,
                )
                self._enrichment_report = (
                    None
                    if candidate.is_cdstub
                    else build_enrichment_report(
                        candidate,
                        toc_durations_ms=(
                            self._sheet.identity.toc.track_durations_ms
                            if self._sheet.identity.toc is not None
                            else None
                        ),
                    )
                )
                self._fill_identify_ui(None, None)
                if not candidate.is_cdstub:
                    self.lbl_id_status.setText(
                        "Édition confirmée par votre sélection; vérifiez la fiche avant de continuer."
                    )
                self._refresh_w3()
                self._start_edition_enrichment(candidate)
            return
        log.info(
            "AVM28E_TRACE edition_selected index=%d candidate=%s album=%r artist=%r year=%s",
            index,
            candidate.selection_key,
            candidate.title,
            candidate.artist_credit,
            candidate.year,
        )
        overrides = self._candidate_manual_overrides(candidate)
        if overrides:
            fields = ", ".join(item[2] for item in overrides[:6])
            if len(overrides) > 6:
                fields += f" et {len(overrides) - 6} autre(s)"
            answer = QMessageBox.question(
                self,
                "Remplacer des corrections ?",
                f"Cette édition modifiera vos corrections pour : {fields}. Continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._candidate_loading = True
                self.combo_editions.blockSignals(True)
                self.combo_editions.setCurrentIndex(
                    self.combo_editions.findData(self._selected_candidate_id)
                )
                self.combo_editions.blockSignals(False)
                self._candidate_loading = False
                return
            for field_meta, key, _label in overrides:
                old_meta = field_meta[key]
                field_meta[key] = FieldMeta(
                    trust=FieldTrust.AMBIGUOUS,
                    provenance=old_meta.provenance,
                    note=old_meta.note,
                )
        if self._sheet.approval == ApprovalState.APPROVED:
            revoke_approval(
                self._sheet,
                note="Édition modifiée — réapprobation requise.",
            )
            self._approved_fp = None
        apply_release_candidate(
            self._sheet,
            candidate,
            user_selected=not candidate.is_cdstub,
            replace_candidate=True,
        )
        self._manual_edition_choice_required = False
        cover_meta = self._sheet.edition.field_meta.get("cover_status")
        if not (
            cover_meta is not None
            and cover_meta.trust == FieldTrust.CONFIRMED
            and cover_meta.provenance in (MetadataProvenance.MANUAL, MetadataProvenance.USER_CORRECTION)
        ):
            self._sheet.edition.cover_status = CoverStatus.MISSING
            self._sheet.edition.cover_path_or_url = None
            self._sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.MISSING)
        self._selected_candidate_id = candidate.selection_key
        self._enrichment_report = (
            None
            if candidate.is_cdstub
            else build_enrichment_report(
                candidate,
                toc_durations_ms=(
                    self._sheet.identity.toc.track_durations_ms
                    if self._sheet.identity.toc is not None
                    else None
                ),
            )
        )
        self._fill_identify_ui(None, None)
        self.lbl_id_status.setText(
            "Données CD stub chargées comme proposition non confirmée."
            if candidate.is_cdstub
            else "Édition mise à jour. Vos autres corrections sont conservées."
        )
        self._refresh_w3()
        log.info(
            "AVM28E_TRACE widgets_refreshed source=edition selected=%s album=%r "
            "artist=%r year=%s tracks=%d path_rows=%d",
            self.combo_editions.currentData(),
            self.edit_album.text(),
            self.edit_artist.text(),
            self.spin_year.value() or None,
            self.table.rowCount(),
            len(self.lbl_path_preview.text().splitlines()),
        )
        self._start_edition_enrichment(candidate)

    def _on_edition_activated(self, index: int) -> None:
        if self._manual_edition_choice_required:
            self._on_edition_selected(index)

    def _start_edition_enrichment(self, candidate: ReleaseCandidate) -> None:
        if candidate.is_cdstub or not candidate.release_id:
            return
        release_id = candidate.release_id
        if release_id in self._enrichment_jobs:
            return
        current_pixmap = self.cover_label.pixmap()
        if current_pixmap is None or current_pixmap.isNull():
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("Chargement…")
        self.cover_label.setToolTip("Recherche et chargement de la pochette…")
        toc_durations = (
            self._sheet.identity.toc.track_durations_ms
            if self._sheet is not None and self._sheet.identity.toc is not None
            else None
        )
        worker = EditionEnrichmentWorker(
            candidate,
            toc_durations_ms=toc_durations,
        )
        worker.finished.connect(self._on_edition_enrichment_ready)
        worker.failed.connect(self._on_edition_enrichment_failed)
        thread = attach_worker_thread(
            worker,
            on_cleared=lambda key=release_id, target=worker: self._clear_enrichment_job(
                key, target
            ),
        )
        self._enrichment_jobs[release_id] = (thread, worker)
        thread.start()

    def _clear_enrichment_job(
        self,
        release_id: str,
        worker: EditionEnrichmentWorker,
    ) -> None:
        current = self._enrichment_jobs.get(release_id)
        if current is not None and current[1] is worker:
            self._enrichment_jobs.pop(release_id, None)

    def _on_edition_enrichment_ready(
        self,
        release_id: str,
        cover: object,
        cover_path: object,
        report: object,
    ) -> None:
        if (
            self._sheet is None
            or self._selected_candidate_id != release_id
            or self._sheet.edition.musicbrainz_release_id != release_id
        ):
            return
        if isinstance(report, EnrichmentReport):
            self._enrichment_report = report
        if self._sheet.approval != ApprovalState.APPROVED and cover is not None:
            cover_meta = self._sheet.edition.field_meta.get("cover_status", FieldMeta())
            user_locked = (
                cover_meta.trust == FieldTrust.CONFIRMED
                and cover_meta.provenance in (
                    MetadataProvenance.MANUAL,
                    MetadataProvenance.USER_CORRECTION,
                )
            )
            if not user_locked:
                displayed = bool(
                    cover_path
                    and Path(str(cover_path)).is_file()
                    and self._show_cover_path(Path(str(cover_path)))
                )
                if not displayed:
                    for image_url in (cover.thumbnail_url, cover.front_url):
                        if image_url and self._load_cover(image_url):
                            displayed = True
                            break
                source = (
                    MetadataProvenance.DISCOGS
                    if cover.source.casefold() == "discogs"
                    else MetadataProvenance.COVER_ART_ARCHIVE
                )
                if cover.status == "confirmed" and cover.front_url and displayed:
                    self._sheet.edition.cover_status = CoverStatus.CONFIRMED
                    self._sheet.edition.cover_path_or_url = cover.front_url
                    self._sheet.edition.field_meta["cover_status"] = FieldMeta(
                        trust=FieldTrust.CONFIRMED,
                        provenance=source,
                        note=cover.message,
                    )
                    self.cover_label.setToolTip(f"Pochette — {cover.source}")
                else:
                    self._load_cover(None)
                    self._sheet.edition.cover_status = CoverStatus.UNAVAILABLE
                    self._sheet.edition.cover_path_or_url = None
                    unavailable_message = cover.message
                    if cover.status == "confirmed":
                        unavailable_message = (
                            f"L’image fournie par {cover.source} n’a pas pu être décodée."
                        )
                    self._sheet.edition.field_meta["cover_status"] = FieldMeta(
                        trust=FieldTrust.UNAVAILABLE,
                        provenance=source,
                        note=unavailable_message,
                    )
                    self.cover_label.setToolTip(
                        f"Pochette indisponible : {unavailable_message}"
                    )
                    current_status = self.lbl_id_status.text().strip()
                    if "pochette" not in current_status.casefold():
                        self.lbl_id_status.setText(
                            f"{current_status} — Pochette indisponible : {unavailable_message}"
                            if current_status
                            else f"Pochette indisponible : {unavailable_message}"
                        )
                    self.cover_label.setText("Pochette indisponible")
        if self._stack.currentIndex() == self.PAGE_REVIEW:
            self._refresh_w3()

    def _on_edition_enrichment_failed(self, release_id: str, message: str) -> None:
        if self._selected_candidate_id == release_id:
            self.lbl_id_status.setText(
                "Les métadonnées sont chargées; la pochette ou les sources secondaires sont indisponibles."
            )
            self.lbl_id_status.setToolTip(message)

    # --- W3 ---
    def _build_w3(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.edit_artist = QLineEdit()
        self.edit_artist.setAccessibleName("Artiste de l’album")
        self.edit_album = QLineEdit()
        self.edit_album.setAccessibleName("Titre de l’album")
        self.spin_year = QSpinBox()
        self.spin_year.setRange(0, 2100)
        self.spin_year.setSpecialValueText("Inconnue")
        self.spin_year.setAccessibleName("Année de l’édition")
        self.chk_year_unavailable = QCheckBox("Année inconnue")
        self.chk_year_unavailable.setAccessibleName("L’année de cette édition est inconnue")
        year_row = QWidget()
        year_layout = QHBoxLayout(year_row)
        year_layout.setContentsMargins(0, 0, 0, 0)
        year_layout.setSpacing(10)
        year_layout.addWidget(self.spin_year)
        year_layout.addWidget(self.chk_year_unavailable)
        year_layout.addStretch(1)
        self._year_row = year_row
        self.edit_year_unavailable_reason = QLineEdit()
        self.edit_year_unavailable_reason.setPlaceholderText(
            "Pourquoi l’année de cette édition est inconnue ?"
        )
        self.edit_year_unavailable_reason.setAccessibleName("Justification de l’année inconnue")
        self.edit_year_unavailable_reason.hide()
        self.chk_compilation = QCheckBox("Compilation")
        self.chk_compilation.setTristate(True)
        self.chk_compilation.setAccessibleName("Cet album est une compilation")
        self.edit_label = QLineEdit()
        self.edit_catalog = QLineEdit()
        self.edit_country = QLineEdit()
        self.spin_disc_number = QSpinBox()
        self.spin_disc_number.setRange(1, 99)
        self.spin_disc_number.setAccessibleName("Numéro du disque dans le coffret")
        self.spin_disc_total = QSpinBox()
        self.spin_disc_total.setRange(1, 99)
        self.spin_disc_total.setAccessibleName("Nombre total de disques du coffret")
        form.addRow("", self.edit_year_unavailable_reason)
        form.addRow("Label", self.edit_label)
        form.addRow("N° catalogue", self.edit_catalog)
        form.addRow("Pays", self.edit_country)
        disc_row = QWidget()
        disc_layout = QHBoxLayout(disc_row)
        disc_layout.setContentsMargins(0, 0, 0, 0)
        disc_layout.setSpacing(8)
        disc_layout.addWidget(QLabel("Disque"))
        disc_layout.addWidget(self.spin_disc_number)
        disc_layout.addWidget(QLabel("sur"))
        disc_layout.addWidget(self.spin_disc_total)
        disc_layout.addStretch(1)
        form.addRow("Coffret", disc_row)
        v.addLayout(form)
        for wdg in (
            self.edit_artist,
            self.edit_album,
            self.edit_label,
            self.edit_catalog,
            self.edit_country,
        ):
            wdg.textChanged.connect(self._on_sheet_edited)
        self.spin_year.valueChanged.connect(self._on_sheet_edited)
        self.spin_disc_number.valueChanged.connect(self._on_sheet_edited)
        self.spin_disc_total.valueChanged.connect(self._on_sheet_edited)
        self.chk_year_unavailable.toggled.connect(self._on_year_unavailable_toggled)
        self.edit_year_unavailable_reason.textChanged.connect(self._on_sheet_edited)
        self.chk_compilation.stateChanged.connect(self._on_sheet_edited)

        self.lbl_tracks_title = QLabel("Pistes")
        self.lbl_tracks_title.setObjectName("cardTitle")
        v.addWidget(self.lbl_tracks_title)
        self.table = QTableWidget(0, 4)
        self.table.setAccessibleName("Pistes de l’album")
        self.table.setHorizontalHeaderLabels(["#", "Titre", "Artiste", "Durée"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setMinimumHeight(72)
        self.table.itemChanged.connect(self._on_sheet_edited)
        v.addWidget(self.table)
        self.lbl_destination_title = QLabel("Destination")
        self.lbl_destination_title.setObjectName("cardTitle")
        v.addWidget(self.lbl_destination_title)
        self.lbl_destination = QLabel(self._config.library_root)
        self.lbl_destination.setWordWrap(True)
        self.lbl_destination.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_destination.setAccessibleName("Dossier de la bibliothèque")
        v.addWidget(self.lbl_destination)
        self.lbl_path_preview = QLabel("")
        self.lbl_path_preview.setWordWrap(True)
        self.lbl_path_preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_path_preview.setProperty("role", "muted")
        self.lbl_path_preview.setAccessibleName("Aperçu du dossier et des pistes")
        v.addWidget(self.lbl_path_preview)
        self.lbl_val = QLabel("")
        self.lbl_val.setWordWrap(True)
        self.lbl_val.setProperty("role", "warning")
        self.lbl_val.hide()
        v.addWidget(self.lbl_val)
        self.lbl_approval = QLabel("")
        self.lbl_approval.setProperty("role", "muted")
        v.addWidget(self.lbl_approval)
        self.lbl_sources = QLabel("")
        self.lbl_sources.setWordWrap(True)
        self.lbl_sources.setProperty("role", "muted")
        self.lbl_sources.setAccessibleName("Sources des informations")
        v.addWidget(self.lbl_sources)
        self.btn_save_draft = QPushButton("Enregistrer le brouillon")
        self.btn_save_draft.setProperty("ghost", True)
        self.btn_save_draft.clicked.connect(self._save_draft)
        v.addWidget(self.btn_save_draft, alignment=Qt.AlignmentFlag.AlignLeft)
        return w

    def _w3_form_widgets(self) -> list:
        return [
            self.edit_artist,
            self.edit_album,
            self.spin_year,
            self.chk_year_unavailable,
            self.edit_year_unavailable_reason,
            self.chk_compilation,
            self.edit_label,
            self.edit_catalog,
            self.edit_country,
            self.spin_disc_number,
            self.spin_disc_total,
            self.table,
        ]

    def _refresh_w3(self) -> None:
        """Charge la fiche courante dans le formulaire W3 sans réécrire la fiche.

        Cause AVM-06C-F1 : ``setText`` / ``setValue`` émettaient ``textChanged`` /
        ``valueChanged`` → ``_on_sheet_edited`` → ``_apply_form_to_sheet`` avec une
        table encore vide, ce qui écrasait ``sheet.tracks`` et les champs edition.
        """
        if not self._sheet:
            return
        self._w3_loading = True
        for wdg in self._w3_form_widgets():
            wdg.blockSignals(True)
        try:
            s = self._sheet
            self.edit_artist.setText(s.edition.album_artist or "")
            self.edit_album.setText(s.edition.album_title or "")
            self.spin_year.setValue(s.edition.year or 0)
            self.chk_year_unavailable.setChecked(
                s.edition.field_meta.get("year", FieldMeta()).trust
                == FieldTrust.UNAVAILABLE
            )
            self.edit_year_unavailable_reason.setText(
                s.edition.year_unavailable_justification or ""
            )
            self.chk_compilation.setCheckState(
                Qt.CheckState.Checked
                if s.edition.field_meta.get("is_compilation", FieldMeta()).trust
                == FieldTrust.CONFIRMED
                and s.edition.is_compilation
                else Qt.CheckState.Unchecked
                if s.edition.field_meta.get("is_compilation", FieldMeta()).trust
                == FieldTrust.CONFIRMED
                else Qt.CheckState.PartiallyChecked
            )
            self._update_compilation_control()
            self.edit_label.setText(s.edition.label or "")
            self.edit_catalog.setText(s.edition.catalog_number or "")
            self.edit_country.setText(s.edition.country or "")
            self.spin_disc_number.setValue(s.disc.disc_number)
            self.spin_disc_total.setValue(s.disc.disc_total)
            self.table.setRowCount(0)
            for t in sorted(s.tracks, key=lambda x: x.number):
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(t.number)))
                self.table.setItem(r, 1, QTableWidgetItem(t.title or ""))
                self.table.setItem(r, 2, QTableWidgetItem(t.artist or ""))
                duration = QTableWidgetItem(
                    f"{t.duration_ms // 60_000}:{(t.duration_ms // 1_000) % 60:02d}"
                )
                duration.setData(Qt.ItemDataRole.UserRole, t.duration_ms)
                duration.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self.table.setItem(r, 3, duration)
                self.table.item(r, 0).setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
        finally:
            for wdg in self._w3_form_widgets():
                wdg.blockSignals(False)
            self._w3_loading = False
        self.spin_year.setEnabled(not self.chk_year_unavailable.isChecked())
        self.edit_year_unavailable_reason.setEnabled(
            self.chk_year_unavailable.isChecked()
        )
        self.edit_year_unavailable_reason.setVisible(
            self.chk_year_unavailable.isChecked()
        )
        table_height = (
            self.table.horizontalHeader().height()
            + self.table.rowCount() * self.table.verticalHeader().defaultSectionSize()
            + 2 * self.table.frameWidth()
            + 4
        )
        self.table.setFixedHeight(max(72, table_height))
        self.lbl_destination.setText(self._config.library_root)
        self._validate_ui()
        if self._enrichment_report is not None:
            sources = sorted({item.source for item in self._enrichment_report.proposals})
            self.lbl_sources.setText("Sources : " + " · ".join(sources) if sources else "")
            self.lbl_sources.setVisible(bool(sources))
        else:
            self.lbl_sources.clear()
            self.lbl_sources.hide()

    def _on_year_unavailable_toggled(self, unavailable: bool) -> None:
        self.spin_year.setEnabled(not unavailable)
        self.edit_year_unavailable_reason.setEnabled(unavailable)
        self.edit_year_unavailable_reason.setVisible(unavailable)
        self._on_sheet_edited()

    def _update_compilation_control(self) -> None:
        if self._sheet is None:
            return
        meta = self._sheet.edition.field_meta.get("is_compilation", FieldMeta())
        uncertain = meta.trust != FieldTrust.CONFIRMED
        self.chk_compilation.setText(
            "Compilation à confirmer" if uncertain else "Compilation"
        )
        self.chk_compilation.setToolTip(
            "Les informations disponibles ne permettent pas de confirmer ce point."
            if uncertain
            else ""
        )
        self.chk_compilation.setAccessibleName(
            "Compilation à confirmer" if uncertain else "Cet album est une compilation"
        )

    def _proposal_source_note(self, field: str, value) -> str:
        report = self._enrichment_report
        if report is None:
            return ""
        aliases = {
            "year": "year (édition précise)",
            "label": "label / numéro de catalogue",
            "catalog_number": "label / numéro de catalogue",
        }
        target = aliases.get(field, field)
        sources = [
            f"{item.source} {item.source_url}"
            for item in report.proposals
            if item.field == target
            and (
                item.value == value
                or field in ("year", "is_compilation")
            )
        ]
        return "Sources proposées: " + "; ".join(dict.fromkeys(sources)) if sources else ""

    def _apply_form_to_sheet(self) -> None:
        if not self._sheet or self._w3_loading:
            return
        s = self._sheet

        def apply_manual_value(attr: str, value, key: str) -> None:
            old = getattr(s.edition, attr)
            if old == value:
                return
            s.record_correction(
                f"edition.{attr}",
                old,
                value,
                note="Modification du formulaire",
                provenance=MetadataProvenance.USER_CORRECTION,
            )
            setattr(s.edition, attr, value)
            s.edition.field_meta[key] = FieldMeta(
                trust=FieldTrust.CONFIRMED,
                provenance=MetadataProvenance.USER_CORRECTION,
                note=self._proposal_source_note(key, value),
            )

        apply_manual_value("album_artist", self.edit_artist.text().strip(), "album_artist")
        apply_manual_value("album_title", self.edit_album.text().strip(), "album_title")

        if self.chk_year_unavailable.isChecked():
            reason = self.edit_year_unavailable_reason.text().strip()
            if s.edition.year is not None:
                s.record_correction(
                    "edition.year",
                    s.edition.year,
                    None,
                    note="Année de l’édition déclarée indisponible",
                    provenance=MetadataProvenance.USER_CORRECTION,
                )
            s.edition.year = None
            s.edition.year_unavailable_justification = reason
            s.edition.field_meta["year"] = FieldMeta(
                trust=FieldTrust.UNAVAILABLE,
                provenance=MetadataProvenance.USER_CORRECTION,
                note=" ".join(
                    part
                    for part in (
                        reason,
                        self._proposal_source_note("year", None),
                    )
                    if part
                ),
            )
        else:
            year = self.spin_year.value()
            s.edition.year_unavailable_justification = None
            if year > 0:
                apply_manual_value("year", year, "year")
            elif s.edition.year is not None:
                apply_manual_value("year", None, "year")
                s.edition.field_meta["year"] = FieldMeta(trust=FieldTrust.MISSING)

        compilation_state = self.chk_compilation.checkState()
        if compilation_state != Qt.CheckState.PartiallyChecked:
            compilation = compilation_state == Qt.CheckState.Checked
            if (
                s.edition.is_compilation != compilation
                or s.edition.field_meta.get("is_compilation", FieldMeta()).trust
                != FieldTrust.CONFIRMED
            ):
                old = s.edition.is_compilation
                s.record_correction(
                    "edition.is_compilation",
                    old,
                    compilation,
                    note="Classification confirmée dans le formulaire",
                    provenance=MetadataProvenance.USER_CORRECTION,
                )
                s.edition.is_compilation = compilation
                s.edition.field_meta["is_compilation"] = FieldMeta(
                    trust=FieldTrust.CONFIRMED,
                    provenance=MetadataProvenance.USER_CORRECTION,
                    note=self._proposal_source_note("is_compilation", compilation),
                )

        for attr, key, value in (
            ("label", "label", self.edit_label.text().strip() or None),
            ("catalog_number", "catalog_number", self.edit_catalog.text().strip() or None),
            ("country", "country", self.edit_country.text().strip() or None),
        ):
            apply_manual_value(attr, value, key)
        for attr, key, value in (
            ("disc_number", "disc_number", self.spin_disc_number.value()),
            ("disc_total", "disc_total", self.spin_disc_total.value()),
        ):
            old = getattr(s.disc, attr)
            if old != value:
                s.record_correction(
                    f"disc.{attr}",
                    old,
                    value,
                    note="Modification du formulaire",
                    provenance=MetadataProvenance.USER_CORRECTION,
                )
                setattr(s.disc, attr, value)
                s.disc.field_meta[key] = FieldMeta(
                    trust=FieldTrust.CONFIRMED,
                    provenance=MetadataProvenance.USER_CORRECTION,
                )
        if s.edition.cover_status == CoverStatus.MISSING and s.edition.cover_path_or_url:
            s.edition.cover_status = CoverStatus.CONFIRMED
            s.edition.field_meta["cover_status"] = _confirmed()
        elif s.edition.cover_status == CoverStatus.MISSING:
            # allow unavailable with note for approve path demos
            pass
        s.disc.field_meta.setdefault("disc_number", _confirmed())
        s.disc.field_meta.setdefault("disc_total", _confirmed())
        if s.identity.toc:
            s.identity.field_meta["toc"] = FieldMeta(
                trust=FieldTrust.CONFIRMED, provenance=MetadataProvenance.TOC
            )
        if s.identity.disc_id:
            s.identity.field_meta["disc_id"] = FieldMeta(
                trust=FieldTrust.CONFIRMED, provenance=MetadataProvenance.TOC
            )
        # Ne jamais remplacer les pistes par une table vide pendant un refresh partiel
        if self.table.rowCount() == 0 and s.tracks:
            s.touch()
            return
        new_tracks: list[TrackMetadata] = []
        for row in range(self.table.rowCount()):
            num = int(self.table.item(row, 0).text())
            title = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
            artist = self.table.item(row, 2).text().strip() if self.table.item(row, 2) else ""
            duration_item = self.table.item(row, 3)
            dur = int(duration_item.data(Qt.ItemDataRole.UserRole) or 0) if duration_item else 0
            previous = next((track for track in s.tracks if track.number == num), None)
            new_track = TrackMetadata(
                number=num,
                title=title,
                artist=artist,
                duration_ms=dur,
                isrc=previous.isrc if previous else None,
                musicbrainz_recording_id=(
                    previous.musicbrainz_recording_id if previous else None
                ),
                musicbrainz_track_id=(
                    previous.musicbrainz_track_id if previous else None
                ),
                field_meta=dict(previous.field_meta) if previous else {},
            )
            for key, old_value, new_value in (
                ("title", previous.title if previous else "", title),
                ("artist", previous.artist if previous else "", artist),
                ("duration_ms", previous.duration_ms if previous else 0, dur),
            ):
                if old_value != new_value:
                    new_track.field_meta[key] = FieldMeta(
                        trust=FieldTrust.CONFIRMED,
                        provenance=MetadataProvenance.USER_CORRECTION,
                    )
                elif key not in new_track.field_meta:
                    new_track.field_meta[key] = (
                        FieldMeta(
                            trust=FieldTrust.CONFIRMED,
                            provenance=MetadataProvenance.TOC,
                        )
                        if key == "duration_ms"
                        else _confirmed()
                    )
            new_tracks.append(new_track)
        s.tracks = new_tracks
        s.touch()

    def _on_sheet_edited(self, *_args) -> None:
        if not self._sheet or self._w3_loading:
            return
        if self._stack.currentIndex() != self.PAGE_REVIEW:
            return
        self._apply_form_to_sheet()
        self._update_compilation_control()
        if self._approved_fp and self._sheet.approval == ApprovalState.APPROVED:
            still, msg = sync_approval_with_fingerprint(self._sheet, self._approved_fp)
            if not still:
                self._approved_fp = None
                if msg:
                    self.lbl_val.setText(msg)
        self._validate_ui()

    def _validate_ui(self) -> None:
        if not self._sheet:
            return
        # ensure cover can be unavailable for approval if still missing
        if self._sheet.edition.cover_status == CoverStatus.MISSING:
            self._sheet.edition.cover_status = CoverStatus.UNAVAILABLE
            self._sheet.edition.field_meta["cover_status"] = FieldMeta(
                trust=FieldTrust.UNAVAILABLE,
                provenance=MetadataProvenance.MANUAL,
                note="Pochette non confirmée à l’approbation",
            )
        result = apply_validation(self._sheet)
        self._sheet.path_preview = build_path_preview(self._sheet)
        self.lbl_path_preview.setText("\n".join(self._sheet.path_preview))
        lines = []
        if result.errors:
            lines.append("Erreurs :")
            lines.extend(f"• {e}" for e in result.errors)
        merged_warns: list[str] = []
        seen: set[str] = set()
        for w in list(result.warnings) + list(self._advisory_warnings):
            if w and w not in seen:
                seen.add(w)
                merged_warns.append(w)
        if merged_warns:
            lines.append("Avertissements :")
            lines.extend(f"• {w}" for w in merged_warns[:8])
        self.lbl_val.setText("\n".join(lines))
        self.lbl_val.setVisible(bool(lines))
        self.lbl_approval.setText(
            "Fiche approuvée" if self._sheet.approval == ApprovalState.APPROVED else ""
        )

    def _save_draft(self) -> None:
        if not self._sheet:
            return
        self._apply_form_to_sheet()
        self._validate_ui()
        self._repo.save(self._sheet)
        QMessageBox.information(self, "Brouillon", "Fiche enregistrée.")

    def _existing_album_path(self, assessment) -> Path | None:
        for hit in assessment.hits:
            if hit.path and hit.path_exists:
                return Path(hit.path)
        return None

    def _open_existing_album(self, assessment) -> bool:
        path = self._existing_album_path(assessment)
        if path is None:
            return False
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        return True

    def _advise_duplicates_on_disc_read(
        self, disc_id: str, expected_track_count: int | None = None
    ) -> None:
        """Gate 1 : bandeau non bloquant (pas de modal — démarrage app fluide)."""
        assessment = assess_duplicates(
            self._db,
            disc_id=disc_id,
            expected_track_count=expected_track_count,
        )
        if self._lbl_dup_w1 is None:
            return
        if assessment.gate == DuplicateGate.ALLOW:
            self._lbl_dup_w1.setText("")
            self._lbl_dup_w1.setProperty("role", "muted")
        else:
            self._lbl_dup_w1.setProperty("role", "banner")
            self._lbl_dup_w1.setText(
                format_assessment_for_user(assessment)
                + "\n\nAction conseillée : ouvrir l’album existant depuis "
                "Ma bibliothèque. Un réarchivage restera possible plus tard, "
                "uniquement après confirmation explicite."
            )
        self._lbl_dup_w1.style().unpolish(self._lbl_dup_w1)
        self._lbl_dup_w1.style().polish(self._lbl_dup_w1)

    def _prompt_rearchive_if_needed(self) -> bool:
        """
        Gate 3 — privilégie « Ouvrir l’album existant » ;
        réarchivage volontaire = action secondaire confirmée.
        """
        if not self._sheet:
            return False
        assessment = assess_from_sheet(self._db, self._sheet)
        if assessment.gate == DuplicateGate.ALLOW:
            return True
        if assessment.gate == DuplicateGate.DENY:
            QMessageBox.critical(
                self,
                "Archivage impossible",
                format_assessment_for_user(assessment),
            )
            return False
        if assessment.gate == DuplicateGate.WARN:
            if self.lbl_w4_dup is not None:
                self.lbl_w4_dup.setText(format_assessment_for_user(assessment))
                self.lbl_w4_dup.setProperty("role", "banner")
                self.lbl_w4_dup.style().unpolish(self.lbl_w4_dup)
                self.lbl_w4_dup.style().polish(self.lbl_w4_dup)
            return True

        # REQUIRE_CONFIRM
        ed = self._sheet.edition
        detail = format_assessment_for_user(assessment)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Album déjà dans votre bibliothèque")
        box.setText(
            f"{ed.album_artist or '?'} — {ed.album_title or '?'} "
            f"({ed.year or '?'}).\n"
            "Cet album semble déjà archivé et présent."
        )
        box.setInformativeText(
            detail
            + "\n\nRecommandé : ouvrir l’album existant. "
            "Le réarchivage crée une nouvelle copie (aucun écrasement silencieux)."
        )
        btn_open = box.addButton(
            "Ouvrir l’album existant", QMessageBox.ButtonRole.AcceptRole
        )
        btn_rearchive = box.addButton(
            "Réarchiver volontairement…", QMessageBox.ButtonRole.DestructiveRole
        )
        box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_open)
        waiting_message = "En attente de votre confirmation concernant un album déjà présent."
        self.lbl_progress.setText(waiting_message)
        self.archive_status_changed.emit(waiting_message, None, False)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_open:
            if not self._open_existing_album(assessment):
                QMessageBox.information(
                    self,
                    "Album",
                    "Dossier introuvable — consultez Ma bibliothèque.",
                )
            self._confirmed_rearchive = False
            finished_message = "Album existant ouvert; aucune extraction n’a démarré."
            self.lbl_progress.setText(finished_message)
            self.archive_status_changed.emit(finished_message, None, False)
            return False
        if clicked is btn_rearchive:
            confirm = QMessageBox.question(
                self,
                "Confirmer le réarchivage",
                "Créer une nouvelle copie de cet album dans la bibliothèque ?\n"
                "L’album existant ne sera pas écrasé.",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self._confirmed_rearchive = True
                return True
        self._confirmed_rearchive = False
        cancelled_message = "Archivage non démarré; la bibliothèque n’a pas été modifiée."
        self.lbl_progress.setText(cancelled_message)
        self.archive_status_changed.emit(cancelled_message, None, False)
        return False

    def _do_approve(self) -> bool:
        if not self._sheet:
            return False
        if self._manual_edition_choice_required:
            message = (
                "Plusieurs éditions différentes correspondent au CD. "
                "Choisissez explicitement l’édition dans la liste avant de continuer."
            )
            self.lbl_id_status.setText(message)
            QMessageBox.information(self, "Choisir l’édition", message)
            return False
        selected_candidate = next(
            (
                candidate
                for candidate in self._candidates
                if candidate.selection_key == self._selected_candidate_id
            ),
            None,
        )
        if (
            selected_candidate is not None
            and selected_candidate.match_source == "toc"
            and not selected_candidate.is_cdstub
        ):
            apply_release_candidate(
                self._sheet,
                selected_candidate,
                user_selected=True,
            )
        self._apply_form_to_sheet()
        self._validate_ui()
        if self._sheet.approval == ApprovalState.APPROVED and self._approved_fp:
            still_approved, message = sync_approval_with_fingerprint(
                self._sheet, self._approved_fp
            )
            if still_approved:
                return True
            self._approved_fp = None
            if message:
                self.lbl_val.setText(message)
                self.lbl_val.setVisible(True)
        try:
            approve_sheet(self._sheet, note="UI wizard Continuer")
        except ApprovalError as exc:
            QMessageBox.warning(self, "Approbation refusée", str(exc))
            self._validate_ui()
            return False
        self._approved_fp = compute_approval_fingerprint(self._sheet)
        self._repo.save(self._sheet)
        self.lbl_approval.setText("Fiche approuvée")
        return True

    def _refresh_w4_preview(self) -> None:
        if not self._sheet:
            return
        ed = self._sheet.edition
        freac_reader = self.combo_drives.currentText() or "Lecteur fre:ac indisponible"
        toc_reader = self._disc_read.device if self._disc_read else "non lu"
        self.lbl_w4_recap.setText(
            f"{ed.album_artist} — {ed.album_title} "
            f"({ed.year or '?'}, {ed.country or '?'})\n"
            "Mode : archivage CD normal\n"
            f"Destination bibliothèque : {self._config.library_root}\n"
            f"Lecteur fre:ac : {freac_reader}\nLecture TOC : {toc_reader}"
        )
        self.lbl_w4_recap.setToolTip(self._config.library_root)
        # Miroir pochette W2 → W4
        if self.cover_label.pixmap() and not self.cover_label.pixmap().isNull():
            self.lbl_w4_cover.setPixmap(
                self.cover_label.pixmap().scaled(
                    160,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.lbl_w4_cover.setText("")
        else:
            self.lbl_w4_cover.setText(ed.album_title or "—")
        assessment = assess_from_sheet(self._db, self._sheet)
        if assessment.gate == DuplicateGate.ALLOW:
            self.lbl_w4_dup.setText("")
            self.lbl_w4_dup.hide()
        else:
            self.lbl_w4_dup.setText(format_assessment_for_user(assessment))
            self.lbl_w4_dup.setProperty("role", "banner")
            self.lbl_w4_dup.style().unpolish(self.lbl_w4_dup)
            self.lbl_w4_dup.style().polish(self.lbl_w4_dup)
            self.lbl_w4_dup.show()

    # --- W4 ---
    def _build_w4(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setSpacing(12)

        self.lbl_w4_dup = QLabel("")
        self.lbl_w4_dup.setWordWrap(True)
        self.lbl_w4_dup.setProperty("role", "banner")
        self.lbl_w4_dup.setAccessibleName("Avertissement doublon avant extraction")
        self.lbl_w4_dup.hide()
        outer.addWidget(self.lbl_w4_dup)

        body = QHBoxLayout()
        body.setSpacing(16)

        # Colonne progression
        left = make_card()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(18, 16, 18, 16)
        lv.setSpacing(10)
        prog_title = QLabel("Extraction et publication")
        prog_title.setObjectName("cardTitle")
        lv.addWidget(prog_title)
        self.lbl_w4_recap = QLabel("—")
        self.lbl_w4_recap.setWordWrap(True)
        lv.addWidget(self.lbl_w4_recap)
        self.chk_reader_pair = QCheckBox(
            "Je confirme que les lecteurs sélectionnés correspondent"
        )
        self.chk_reader_pair.setAccessibleName(
            "Confirmer la correspondance des lecteurs pour l’extraction"
        )
        self.chk_reader_pair.setToolTip(
            "Le lecteur fre:ac utilisé pour le rip doit être le même lecteur Windows "
            "que celui utilisé pour lire la TOC."
        )
        self.chk_reader_pair.hide()
        lv.addWidget(self.chk_reader_pair)
        self.lbl_progress = QLabel("En attente du lancement…")
        self.lbl_progress.setWordWrap(True)
        self.lbl_progress.setStyleSheet("font-size:15px;font-weight:600;color:#F1B65C;")
        self.lbl_progress.setAccessibleName("Message de progression")
        lv.addWidget(self.lbl_progress)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Barre de progression")
        lv.addWidget(self.progress)
        self.lbl_progress_measure = QLabel("Aucune progression active.")
        self.lbl_progress_measure.setObjectName("muted")
        self.lbl_progress_measure.setWordWrap(True)
        self.lbl_progress_measure.setAccessibleName(
            "Disponibilité de la progression chiffrée"
        )
        lv.addWidget(self.lbl_progress_measure)
        self.lbl_track_progress = QLabel("Aucune piste terminée.")
        self.lbl_track_progress.setObjectName("muted")
        self.lbl_track_progress.setWordWrap(True)
        self.lbl_track_progress.setAccessibleName("Pistes terminées")
        lv.addWidget(self.lbl_track_progress)
        steps_lbl = QLabel("Sous-étapes")
        steps_lbl.setObjectName("muted")
        lv.addWidget(steps_lbl)
        self.list_progress_steps = QListWidget()
        self.list_progress_steps.setObjectName("progressSteps")
        self.list_progress_steps.setAccessibleName("Sous-étapes d’archivage")
        self.list_progress_steps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_progress_steps.setMaximumHeight(160)
        self._progress_step_names = list(PIPELINE_STEPS[:-1])
        for name in self._progress_step_names:
            self.list_progress_steps.addItem(f"À venir — {name}")
        lv.addWidget(self.list_progress_steps)
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setProperty("ghost", True)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setAccessibleName("Annuler l’archivage")
        self.btn_cancel.clicked.connect(self._cancel_archive)
        lv.addWidget(self.btn_cancel, alignment=Qt.AlignmentFlag.AlignLeft)
        lv.addStretch(1)

        # Colonne pochette + options
        right = make_card()
        right.setMaximumWidth(340)
        rv = QVBoxLayout(right)
        rv.setContentsMargins(18, 16, 18, 16)
        rv.setSpacing(10)
        self.lbl_w4_cover = QLabel("—")
        self.lbl_w4_cover.setObjectName("coverPlaceholder")
        self.lbl_w4_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_w4_cover.setMinimumHeight(160)
        self.lbl_w4_cover.setAccessibleName("Pochette album")
        rv.addWidget(self.lbl_w4_cover)
        opt = QLabel("Publication dans la bibliothèque")
        opt.setObjectName("cardTitle")
        rv.addWidget(opt)
        self.lbl_collision_policy = QLabel(
            "L’album sera ajouté après vérification. Si le dossier cible existe, "
            "AVM créera un nouveau dossier; aucun fichier existant ne sera remplacé."
        )
        self.lbl_collision_policy.setWordWrap(True)
        self.lbl_collision_policy.setObjectName("muted")
        rv.addWidget(self.lbl_collision_policy)
        rv.addStretch(1)

        body.addWidget(left, 3)
        body.addWidget(right, 2)
        outer.addLayout(body, 1)
        return w

    def _collision_policy(self) -> CollisionPolicy:
        return CollisionPolicy.RENAME

    def _start_archive(self) -> None:
        if not self._sheet:
            return
        try:
            assert_can_start_archive_rip(self._sheet)
        except ApprovalError as exc:
            QMessageBox.warning(self, "Archive bloquée", str(exc))
            return
        if self._disc_read is None:
            QMessageBox.warning(
                self,
                "Lecture du disque",
                "Relisez et identifiez le CD présent avant de lancer l’extraction.",
            )
            return
        if self._reader_pair_required and not self.chk_reader_pair.isChecked():
            QMessageBox.warning(
                self,
                "Correspondance des lecteurs",
                "Confirmez que le lecteur fre:ac choisi est le même lecteur Windows utilisé pour lire la TOC.",
            )
            return
        # Gate 3 — immédiatement avant extraction / publication
        if not self._prompt_rearchive_if_needed():
            return
        st = probe_freaccmd(
            configured_path=self._config.freaccmd_path or None,
            freac_install_dir=self._config.freac_install_dir or None,
            run_probes=False,
        )
        if not st.found or not st.path:
            QMessageBox.warning(
                self,
                "Archivage",
                "L’outil d’extraction est introuvable. Vérifiez Paramètres.",
            )
            return
        if not self._drives:
            QMessageBox.warning(self, "Archivage", "Aucun lecteur CD détecté.")
            return
        drive = self.combo_drives.currentData()
        if drive is None:
            return

        self.lbl_w4_recap.setText(
            f"{self._sheet.edition.album_artist} — {self._sheet.edition.album_title} "
            f"({self._sheet.edition.year or '?'}, {self._sheet.edition.country or '?'}) "
            f"[{self._sheet.approval.value}]\n"
            "Mode : archivage CD normal\n"
            f"Destination bibliothèque : {self._config.library_root}\n"
            f"Lecteur fre:ac : {self.combo_drives.currentText()}\n"
            f"Lecture TOC : {self._disc_read.device if self._disc_read else 'non lue'}"
        )
        self.lbl_w4_recap.setToolTip(self._config.library_root)
        self._reset_archive_tracking()
        self._archive_active = True
        self.lbl_track_progress.setText(
            f"0 piste terminée sur {len(self._sheet.tracks)}"
        )
        self.lbl_progress.setText("Vérification du disque…")
        self._highlight_progress_step(0)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.lbl_progress_measure.setText(
            "Vérification de la TOC et du Disc ID en cours; aucune mesure chiffrée disponible."
        )
        self.archive_status_changed.emit(self.lbl_progress.text(), None, True)
        self._set_busy(True)
        self.btn_cancel.setEnabled(True)

        worker = ArchiveWorker(
            metadata=self._sheet,
            library_root=Path(self._config.library_root),
            jobs_root=Path(self._config.jobs_dir),
            db_path=self._db.path,
            freaccmd=st.path,
            drive_number=int(drive),
            flac_compression=self._config.flac_compression,
            eject_after_rip=self._config.eject_after_rip,
            collision_policy=self._collision_policy(),
            confirm_publish=True,
            optical_device=self._optical_device(),
            # disc_read = contrôle anti-désync ; le pipeline relit toujours le TOC (06G-P1).
            disc_read=self._disc_read,
            confirmed_rearchive=self._confirmed_rearchive,
        )
        self._active_job_id = worker.job_id
        thread = attach_worker_thread(
            worker,
            on_finished=self._on_archive_finished,
            on_failed=self._on_archive_failed,
            on_cleared=lambda job_id=worker.job_id: self._clear_thread(job_id),
            progress_slot=self._on_archive_progress,
        )
        self._thread = thread
        self._worker = worker
        thread.start()

    def _cancel_archive(self) -> None:
        if self._worker is not None and hasattr(self._worker, "cancel"):
            self._worker.cancel()
            self.lbl_progress.setText("Annulation demandée; arrêt à la prochaine frontière sûre…")
            self.archive_status_changed.emit(self.lbl_progress.text(), None, True)

    def shutdown_background_work(self, *, timeout_ms: int = 12_000) -> bool:
        """Annule et attend le worker identify/archive (fermeture fenêtre)."""
        self._media_scan_timer.stop()
        if not shutdown_worker_thread(
            self._media_scan_thread,
            self._media_scan_worker,
            timeout_ms=timeout_ms,
        ):
            return False
        self._media_scan_thread = None
        self._media_scan_worker = None
        for thread, worker in tuple(self._enrichment_jobs.values()):
            if not shutdown_worker_thread(
                thread,
                worker,
                timeout_ms=timeout_ms,
            ):
                return False
        self._enrichment_jobs.clear()
        if not self.dvd.shutdown_background_work(timeout_ms=timeout_ms):
            return False
        ok = shutdown_worker_thread(self._thread, self._worker, timeout_ms=timeout_ms)
        if ok:
            self._clear_thread()
            self._set_busy(False)
        return ok

    def _reset_archive_tracking(self) -> None:
        self._archive_active = False
        self._completed_track_numbers.clear()
        self._last_progress_step = -1
        self._highlight_progress_step(-1)
        self.lbl_progress.setText("En attente du lancement…")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.lbl_progress_measure.setText("Aucune progression active.")
        self.lbl_track_progress.setText("Aucune piste terminée.")
        self.archive_status_changed.emit("", None, False)

    def _highlight_progress_step(
        self,
        index: int,
        *,
        completed: bool = False,
        failed: bool = False,
        warning: bool = False,
        skipped: bool = False,
    ) -> None:
        self._last_progress_step = index
        for i in range(self.list_progress_steps.count()):
            item = self.list_progress_steps.item(i)
            font = item.font()
            active = i == index and not (completed or failed or warning or skipped)
            font.setBold(active or (i == index and (failed or warning)))
            item.setFont(font)
            if skipped and i == index:
                state = "Ignorée — dossier déjà présent"
                item.setForeground(Qt.GlobalColor.darkYellow)
            elif failed and i == index:
                state = "Échec"
                item.setForeground(Qt.GlobalColor.red)
            elif warning and i == index:
                state = "Terminée avec avertissements"
                item.setForeground(Qt.GlobalColor.darkYellow)
            elif completed:
                state = "Réussie"
                item.setForeground(Qt.GlobalColor.darkGreen)
            elif i < index:
                state = "Réussie"
                item.setForeground(Qt.GlobalColor.darkGreen)
            elif active:
                state = "En cours"
                item.setForeground(Qt.GlobalColor.darkBlue)
                self.list_progress_steps.setCurrentRow(i)
            else:
                state = "À venir"
                item.setForeground(Qt.GlobalColor.gray)
            item.setText(f"{state} — {self._progress_step_names[i]}")

    def _track_titles_for_progress(self) -> list[str]:
        if not self._sheet:
            return []
        return [
            (t.title or "").strip()
            for t in sorted(self._sheet.tracks, key=lambda x: x.number)
        ]

    def _on_archive_progress(
        self, message: str, fraction: object, job_id: str | None = None
    ) -> None:
        if job_id is not None and job_id != self._active_job_id:
            return
        raw = str(message)
        titles = self._track_titles_for_progress()
        track_total = len(titles)
        completed_track = parse_completed_track_number(raw)
        track_number = parse_track_number_from_progress(raw)
        if completed_track is not None:
            self._completed_track_numbers.add(completed_track)
            title = (
                titles[completed_track - 1]
                if 1 <= completed_track <= len(titles) and titles[completed_track - 1]
                else "titre non déterminé"
            )
            label = f"Piste {completed_track}/{track_total} terminée — {title}"
        else:
            label = map_progress_message(
                raw,
                track_titles=titles,
                track_total=track_total or None,
            )
            if track_number is not None and track_total:
                title = (
                    titles[track_number - 1]
                    if 1 <= track_number <= len(titles) and titles[track_number - 1]
                    else "titre non déterminé"
                )
                label = (
                    f"Piste {track_number}/{track_total} signalée par fre:ac — {title}; "
                    "fin non confirmée"
                )
        self.lbl_progress.setText(label)
        if track_total:
            completed = len(self._completed_track_numbers)
            noun = "piste terminée" if completed == 1 else "pistes terminées"
            self.lbl_track_progress.setText(f"{completed} {noun} sur {track_total}")
        idx = progress_step_index(raw, track_titles=titles)
        if idx >= 0:
            # PIPELINE_STEPS inclut « Terminé » ; la liste W4 l’exclut
            self._highlight_progress_step(min(idx, self.list_progress_steps.count() - 1))
        try:
            measured = float(fraction)
        except (TypeError, ValueError):
            measured = -1.0
        if 0.0 <= measured <= 1.0:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(measured * 100))
            self.progress.setTextVisible(True)
            self.progress.setFormat("fre:ac %p%")
            self.lbl_progress_measure.setText(
                "Valeur rapportée par fre:ac; elle ne couvre pas les étapes de vérification/publication restantes."
            )
        else:
            self.progress.setRange(0, 0)
            self.progress.setTextVisible(False)
            self.lbl_progress_measure.setText(
                "Aucune mesure chiffrée globale disponible; l’activité continue et les pistes terminées sont comptées ci-dessus."
            )
        self.archive_status_changed.emit(label, fraction, self._archive_active)

    def _on_archive_failed(self, message: str, job_id: str) -> None:
        if job_id != self._active_job_id:
            return
        self._archive_active = False
        self._set_busy(False)
        self.btn_cancel.setEnabled(False)
        self._last_report = None
        self.lbl_done.setProperty("role", "error")
        self.lbl_done.setText(f"Échec : {message}")
        self.txt_done.setPlainText(message)
        self._highlight_progress_step(max(0, self._last_progress_step), failed=True)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.archive_status_changed.emit(f"Échec de l’archivage : {message}", None, False)
        self._set_step(self.PAGE_DONE)

    def _on_archive_finished(self, report: object) -> None:
        if getattr(report, "job_id", None) != self._active_job_id:
            return
        self._archive_active = False
        self._set_busy(False)
        self.btn_cancel.setEnabled(False)
        assert isinstance(report, ArchiveJobReport)
        self._last_report = report
        published = bool(
            report.publish
            and report.publish.published
            and report.state.startswith("Completed")
        )
        if published:
            self._highlight_progress_step(
                self.list_progress_steps.count() - 1,
                completed=True,
                warning=report.state == "CompletedWithWarnings",
            )
            self.lbl_done.setProperty("role", "success")
            path = report.publish.album_dir if report.publish else None
            self.lbl_done.setText("Album ajouté à votre bibliothèque.")
            lines = [
                "Mode : archivage CD normal",
                "Publication et indexation SQLite : réussies",
                f"Racine bibliothèque : {self._config.library_root}",
                f"État : {report.state}",
                f"Dossier album publié : {path}",
                "",
                "Les fichiers FLAC s’ouvrent dans n’importe quel lecteur compatible.",
                "",
                "Avertissements :",
                *[f"• {w}" for w in report.warnings[:8]],
            ]
            self.txt_done.setPlainText("\n".join(lines))
            self.btn_open_folder.setEnabled(bool(path))
            self.library_changed.emit()
            status = (
                "Archivage terminé avec avertissements."
                if report.state == "CompletedWithWarnings"
                else "Archivage terminé; album publié et vérifié."
            )
            self.archive_status_changed.emit(status, 1.0, False)
        elif report.state == "SkippedDuplicate":
            self._highlight_progress_step(
                self.list_progress_steps.count() - 1, skipped=True
            )
            self.lbl_done.setProperty("role", "warning")
            self.lbl_done.setText("Extraction terminée; album non ajouté à la bibliothèque.")
            self.txt_done.setPlainText(
                f"L’extraction a produit {len(report.rip.flac_files) if report.rip else 0} FLAC, "
                "mais la destination était déjà occupée. Les fichiers restent dans le dossier du job et l’inbox; "
                "aucun fichier existant n’a été remplacé.\n\n"
                f"Dossier job : {report.workdir}\nDossier inbox : {report.inbox_dir or 'aucun'}"
            )
            self.btn_open_folder.setEnabled(False)
            self.archive_status_changed.emit(
                "Extraction terminée; publication ignorée, dossier cible déjà présent.",
                None,
                False,
            )
        else:
            self._highlight_progress_step(
                self._progress_step_for_failure(report.failure_kind), failed=True
            )
            self.lbl_done.setProperty("role", "error")
            self.lbl_done.setText(
                f"Archivage non terminé ({report.state}). "
                "Aucun album n’est déclaré archivé sans publication réussie."
            )
            publication = (
                "Publication : ignorée (doublon déjà présent)"
                if report.publish and report.publish.skipped
                else "Publication : non effectuée"
            )
            lines = [
                "Mode : archivage CD normal",
                f"Racine bibliothèque visée : {self._config.library_root}",
                publication,
                report.error or report.state,
                *report.warnings,
            ]
            self.txt_done.setPlainText("\n".join(lines))
            self.btn_open_folder.setEnabled(False)
            self.archive_status_changed.emit(
                f"Archivage non terminé ({report.state}). {report.error or report.state}",
                None,
                False,
            )
        if published:
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.progress.setTextVisible(True)
            self.progress.setFormat("Terminé")
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.progress.setTextVisible(False)
        self._set_step(self.PAGE_DONE)

    def _progress_step_for_failure(self, failure_kind: object) -> int:
        kind = str(getattr(failure_kind, "value", failure_kind) or "").casefold()
        if "extraction" in kind or "cancel" in kind:
            return 1
        if "integrity" in kind or "decode" in kind:
            return 2
        if "metadata" in kind:
            return 3
        if "publish" in kind:
            return 5
        return max(0, self._last_progress_step)

    # --- W5 ---
    def _build_w5(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.lbl_done = QLabel("—")
        self.lbl_done.setWordWrap(True)
        self.lbl_done.setObjectName("wizardTitle")
        self.lbl_done.setAccessibleName("Résultat de l’archivage")
        v.addWidget(self.lbl_done)
        self.txt_done = QTextEdit()
        self.txt_done.setReadOnly(True)
        self.txt_done.setAccessibleName("Détails du résultat")
        v.addWidget(self.txt_done)
        row = QHBoxLayout()
        self.btn_open_folder = QPushButton("Ouvrir le dossier")
        self.btn_open_folder.setProperty("primary", True)
        self.btn_open_folder.setAccessibleName("Ouvrir le dossier album")
        self.btn_open_folder.clicked.connect(self._open_folder)
        self.btn_goto_history = QPushButton("Voir l’historique")
        self.btn_goto_history.setAccessibleName("Aller à l’historique")
        self.btn_goto_history.clicked.connect(lambda: self.request_navigate.emit(2))
        row.addWidget(self.btn_open_folder)
        row.addWidget(self.btn_goto_history)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)
        return w

    def _open_folder(self) -> None:
        if not self._last_report or not self._last_report.publish:
            return
        path = self._last_report.publish.album_dir
        if path and Path(path).is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(
                self,
                "Dossier",
                "Impossible d’ouvrir le dossier. Vérifiez qu’il existe encore.",
            )

    def _reset_session(self) -> None:
        self._active_job_id = None
        self._disc_read = None
        self._sheet = None
        self._lookup = None
        self._candidates = []
        self._selected_candidate_id = None
        self._manual_edition_choice_required = False
        self._approved_fp = None
        self._advisory_warnings = []
        self._confirmed_rearchive = False
        self._last_report = None
        self._reset_archive_tracking()
        self.lbl_disc.setText("Insérez un CD audio, puis cliquez sur Relire le disque.")
        self.lbl_disc_details.setText("")
        self.lbl_disc_details.hide()
        self.btn_tech_details.setChecked(False)
        self.btn_tech_details.setText("Détails techniques…")
        if self._lbl_dup_w1 is not None:
            self._lbl_dup_w1.setText("")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.archive_busy_changed.emit(busy)
        self.btn_back.setEnabled(not busy and self._stack.currentIndex() > 0)
        if self._stack.currentIndex() != self.PAGE_DONE:
            self.btn_next.setEnabled(not busy)

    def _clear_thread(self, job_id: str | None = None) -> None:
        if job_id is not None and (
            self._worker is None
            or getattr(self._worker, "job_id", None) != job_id
        ):
            return
        self._thread = None
        self._worker = None
