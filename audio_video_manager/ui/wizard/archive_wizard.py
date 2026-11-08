"""Wizard UI-1 : Disque → Identification → Approbation → Extraction → Terminé."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
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
from audio_video_manager.metadata.cover_art import fetch_cover_art_info
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
from audio_video_manager.ui.cover_cache import fetch_cover_to_cache
from audio_video_manager.ui.dvd_extraction_dialog import DvdArchivePanel
from audio_video_manager.ui.identify_worker import IdentifyWorker
from audio_video_manager.ui.thread_lifecycle import (
    attach_worker_thread,
    shutdown_worker_thread,
)
from audio_video_manager.ui.progress_labels import (
    PIPELINE_STEPS,
    map_progress_message,
    progress_step_index,
)
from audio_video_manager.ui.widgets import make_card

log = get_logger("ui.wizard")

STEP_LABELS = (
    "1 Disque",
    "2 Identification",
    "3 Approbation",
    "4 Extraction / publication",
    "5 Terminé",
)
DVD_STEP_LABELS = ("Disque", "Titres et pistes", "Options", "Extraction", "Terminé")


def _confirmed() -> FieldMeta:
    return FieldMeta(trust=FieldTrust.CONFIRMED, provenance=MetadataProvenance.MANUAL)


class ArchiveWizardPage(QWidget):
    """Session wizard conservée lors des changements de section (A3)."""

    status_message = Signal(str)
    archive_busy_changed = Signal(bool)
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
        self._decision_summary = ""
        self._enrichment_report: EnrichmentReport | None = None
        self._candidates: list[ReleaseCandidate] = []
        self._approved_fp: str | None = None
        self._thread: QThread | None = None
        self._worker = None
        self._last_report: ArchiveJobReport | None = None
        self._busy = False
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
        for i, label in enumerate(STEP_LABELS):
            # Libellés courts dans les pastilles
            short = label.split(" ", 1)[-1] if label[:1].isdigit() else label
            btn = QPushButton(short)
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
        self._stack.addWidget(self._build_w3())
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
        self.refresh_drives()

    # --- public ---
    def set_config(self, config: AppConfig) -> None:
        self._config = config
        self.dvd.set_config(config)
        self.refresh_drives()

    def is_busy(self) -> bool:
        return self._busy

    def available_drives(self) -> list[CdDrive]:
        return list(self._drives)

    def current_step(self) -> int:
        return self._dvd_step if self.media_combo.currentIndex() == 1 else self._stack.currentIndex()

    def approval_fingerprint(self) -> str | None:
        return self._approved_fp

    def sheet(self) -> DiscMetadata | None:
        return self._sheet

    def refresh_drives(self) -> None:
        self.combo_drives.clear()
        self._drives = []
        st = probe_freaccmd(
            configured_path=self._config.freaccmd_path or None,
            freac_install_dir=self._config.freac_install_dir or None,
            run_probes=False,
        )
        if not st.found or not st.path:
            self.lbl_disc.setText(
                "L’outil d’extraction est introuvable. "
                "Ouvrez Paramètres pour indiquer son emplacement."
            )
            return
        try:
            self._drives = FreacCdRipper(st.path).list_drives()
        except OSError as exc:
            self.lbl_disc.setText(f"Lecteurs indisponibles : {exc}")
            return
        letters = list_cdrom_device_letters()
        letter = letters[0] if len(letters) == 1 else None
        for d in self._drives:
            self.combo_drives.addItem(d.friendly_label(letter), d.number)
            idx = self.combo_drives.count() - 1
            # Identifiant matériel conservé en info-bulle (hors parcours normal).
            self.combo_drives.setItemData(idx, d.label(), Qt.ItemDataRole.ToolTipRole)
        for i, d in enumerate(self._drives):
            if d.number == self._config.last_drive_number:
                self.combo_drives.setCurrentIndex(i)
                break

    # --- step chrome ---
    def _set_step(self, index: int) -> None:
        if self.media_combo.currentIndex() == 1:
            self._set_dvd_step(index)
            return
        self._stack.setCurrentIndex(index)
        self.media_combo.setVisible(index == 0)
        self.media_label.setVisible(index == 0)
        titles = [
            ("Disque", "Confirmez le lecteur et le CD à archiver."),
            ("Identification", "Vérifiez l’édition proposée."),
            ("Vérifier et approuver", "Corrigez si besoin, puis approuvez explicitement."),
            ("Extraire et publier", "Le CD doit rester le même jusqu’à la fin."),
            ("Terminé", "Résultat de l’archivage."),
        ]
        self._title.setText(titles[index][0])
        self._help.setText(titles[index][1])
        for i, btn in enumerate(self._step_buttons):
            btn.setText(STEP_LABELS[i].split(" ", 1)[-1])
            btn.setAccessibleName(f"Étape {STEP_LABELS[i]}")
            btn.setEnabled(False)
            btn.setProperty("active", "true" if i == index else "false")
            btn.setProperty("done", "true" if i < index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.btn_back.setEnabled(index > 0 and index < 4 and not self._busy)
        if index == 4:
            self.btn_next.setText("Archiver un autre CD")
            self.btn_next.setEnabled(True)
        elif index == 3:
            self.btn_next.setText("Lancer l’archivage")
            self.btn_next.setEnabled(not self._busy)
            self._refresh_w4_preview()
        elif index == 2:
            self.btn_next.setText("Continuer →")
            self.btn_next.setEnabled(not self._busy)
            self._refresh_w3()
        else:
            self.btn_next.setText("Continuer →")
            self.btn_next.setEnabled(not self._busy)

    def _on_media_changed(self, _index: int) -> None:
        self._set_step(0)

    def _set_dvd_step(self, index: int) -> None:
        self._dvd_step = index
        self._stack.setCurrentWidget(self.dvd)
        self.media_combo.setVisible(index == 0)
        self.media_label.setVisible(index == 0)
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
        if cur <= 0:
            return
        # A3 : retour sans edit conserve Approved
        self._set_step(cur - 1)

    def _go_next(self) -> None:
        if self.media_combo.currentIndex() == 1:
            self._go_next_dvd()
            return
        if self._busy and self._stack.currentIndex() != 4:
            return
        cur = self._stack.currentIndex()
        if cur == 0:
            self._read_toc_and_continue()
        elif cur == 1:
            if self._sheet is None:
                QMessageBox.information(self, "Identification", "Identifiez d’abord le disque.")
                return
            self._set_step(2)
        elif cur == 2:
            if not self._sheet or self._sheet.approval != ApprovalState.APPROVED:
                QMessageBox.warning(
                    self,
                    "Approbation",
                    "Approuvez la fiche avant de continuer vers l’extraction.",
                )
                return
            self._set_step(3)
        elif cur == 3:
            self._start_archive()
        elif cur == 4:
            self._reset_session()
            self._set_step(0)

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
        form.addRow("Lecteur :", self.combo_drives)
        v.addLayout(form)
        self.lbl_disc = QLabel("Insérez un CD audio, puis cliquez sur Relire le disque.")
        self.lbl_disc.setWordWrap(True)
        v.addWidget(self.lbl_disc)
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
        btn = QPushButton("Relire le disque")
        btn.setProperty("primary", True)
        btn.setMaximumWidth(280)
        btn.setAccessibleName("Relire le disque")
        btn.clicked.connect(self._on_reread)
        v.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
        v.addStretch(1)
        return w

    def _toggle_tech_details(self, checked: bool) -> None:
        self.lbl_disc_details.setVisible(checked and bool(self.lbl_disc_details.text()))
        self.btn_tech_details.setText(
            "Masquer les détails techniques" if checked else "Détails techniques…"
        )

    def _optical_device(self) -> str | None:
        idx = self.combo_drives.currentIndex()
        designation = None
        if 0 <= idx < len(self._drives):
            designation = self._drives[idx].designation
            self._config.last_drive_number = self._drives[idx].number
        device, reason = resolve_optical_device_for_discid(designation)
        log.info("optical: %s (%s)", device, reason)
        return device

    def _on_reread(self) -> None:
        try:
            self._disc_read = read_disc_toc(self._optical_device())
        except Exception as exc:  # noqa: BLE001
            self.lbl_disc.setText(str(exc))
            self._disc_read = None
            return
        r = self._disc_read
        mins = sum(r.toc.track_durations_ms) // 60000
        self.lbl_disc.setText(
            f"CD détecté — {r.toc.audio_track_count} pistes · environ {mins} minutes"
        )
        self.lbl_disc_details.setText(f"Disc ID : {r.disc_id}")
        self.lbl_disc_details.setToolTip(r.disc_id or "")
        # Visible seulement si l’utilisateur ouvre les détails techniques
        self.lbl_disc_details.setVisible(self.btn_tech_details.isChecked())
        # Gate 1 — lecture initiale (n’empêche jamais le démarrage de l’app)
        self._confirmed_rearchive = False
        self._advise_duplicates_on_disc_read(r.disc_id)
        # A3 identity change
        if self._sheet and self._sheet.identity.disc_id and self._sheet.identity.disc_id != r.disc_id:
            if self._sheet.approval == ApprovalState.APPROVED:
                revoke_approval(
                    self._sheet,
                    note="Le disque a changé. Approuvez à nouveau avant d’extraire.",
                )
                self._approved_fp = None
                QMessageBox.warning(
                    self,
                    "Disque différent",
                    "Le CD lu n’est plus le même que la fiche approuvée. "
                    "L’approbation a été annulée.",
                )
        # Statut local uniquement — le shell restaure l’état outil hors Archivage (06O)
        self.status_message.emit(
            f"CD {r.toc.audio_track_count} pistes · environ {mins} min"
        )

    def _read_toc_and_continue(self) -> None:
        if self._disc_read is None:
            self._on_reread()
        if self._disc_read is None:
            return
        self._set_step(1)
        self._start_identify()

    # --- W2 ---
    def _build_w2(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        top = QHBoxLayout()
        self.cover_label = QLabel()
        self.cover_label.setObjectName("coverPlaceholder")
        self.cover_label.setFixedSize(140, 140)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setAccessibleName("Pochette album")
        self.cover_label.setText("—")
        top.addWidget(self.cover_label)
        meta = QVBoxLayout()
        self.lbl_id_title = QLabel("—")
        self.lbl_id_title.setStyleSheet("font-size:15px;font-weight:600;")
        self.lbl_id_artist = QLabel("—")
        self.lbl_id_meta = QLabel("—")
        self.lbl_id_meta.setWordWrap(True)
        self.lbl_id_meta.setProperty("role", "muted")
        self.lbl_id_note = QLabel(
            "Le pays préféré sert seulement à trancher entre éditions semblables."
        )
        self.lbl_id_note.setWordWrap(True)
        self.lbl_id_note.setProperty("role", "muted")
        self.lbl_id_warn = QLabel("")
        self.lbl_id_warn.setWordWrap(True)
        self.lbl_id_warn.setProperty("role", "warning")
        for wdg in (
            self.lbl_id_title,
            self.lbl_id_artist,
            self.lbl_id_meta,
            self.lbl_id_note,
            self.lbl_id_warn,
        ):
            meta.addWidget(wdg)
        top.addLayout(meta, 1)
        v.addLayout(top)
        v.addWidget(QLabel("Autres éditions"))
        self.list_alts = QListWidget()
        self.list_alts.itemDoubleClicked.connect(self._apply_selected_alt)
        v.addWidget(self.list_alts)
        row = QHBoxLayout()
        apply_btn = QPushButton("Appliquer l’édition sélectionnée")
        apply_btn.clicked.connect(self._apply_selected_alt)
        row.addWidget(apply_btn)
        v.addLayout(row)
        self.lbl_id_status = QLabel("")
        self.lbl_id_status.setWordWrap(True)
        v.addWidget(self.lbl_id_status)
        return w

    def _start_identify(self) -> None:
        self.lbl_id_status.setText("Recherche des informations…")
        self.list_alts.clear()
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
        if self._disc_read is not None:
            if self._approved_fp:
                self._approved_fp = None
            self._sheet = sheet_from_disc_read(self._disc_read)
            self._lookup = None
            self._enrichment_report = None
            self._candidates = []
            self._fill_identify_ui(None, None)
        self.lbl_id_status.setText(
            f"Impossible d’identifier en ligne : {message}\n"
            "Vous pourrez compléter la fiche manuellement à l’étape suivante."
        )

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
        self._decision_summary = getattr(decision, "summary", "") or ""
        self._fill_identify_ui(cover, decision)
        ok, msg = sync_approval_with_fingerprint(self._sheet, self._approved_fp)
        if not ok and msg:
            self._approved_fp = None
            self.lbl_id_warn.setText(msg)

    def _fill_identify_ui(self, cover, decision) -> None:
        assert self._sheet is not None
        ed = self._sheet.edition
        self.lbl_id_title.setText(ed.album_title or "(titre à compléter)")
        self.lbl_id_artist.setText(ed.album_artist or "(artiste à compléter)")
        bits = [
            str(ed.year) if ed.year else None,
            ed.country,
            ed.label,
            ed.catalog_number,
        ]
        selected = getattr(decision, "selected", None)
        first_release_date = getattr(selected, "release_group_first_release_date", None)
        if first_release_date:
            bits.append(f"Groupe : première sortie {first_release_date}")
        self.lbl_id_meta.setText(" · ".join(x for x in bits if x) or "—")
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
        self.lbl_id_status.setText(self._decision_summary)
        self.list_alts.clear()
        for c in self._candidates:
            label = (
                f"{c.artist_credit} — {c.title} "
                f"[{c.country or '?'} {c.date or ''}] "
                f"{('/'.join(c.catalog_numbers)) if c.catalog_numbers else ''}"
            )
            item = QListWidgetItem(label.strip())
            item.setData(Qt.ItemDataRole.UserRole, c.release_id)
            self.list_alts.addItem(item)
        if decision is not None and getattr(decision, "selected", None):
            for i, c in enumerate(self._candidates):
                if c.release_id == decision.selected.release_id:
                    self.list_alts.setCurrentRow(i)
                    break
        url = None
        if cover is not None and getattr(cover, "thumbnail_url", None):
            url = cover.thumbnail_url or cover.front_url
        elif ed.cover_path_or_url and str(ed.cover_path_or_url).startswith("http"):
            url = ed.cover_path_or_url
        self._load_cover(url)

    def _load_cover(self, url: str | None) -> None:
        self.cover_label.setText("—")
        self.cover_label.setPixmap(QPixmap())
        if not url:
            return
        path = fetch_cover_to_cache(url)
        if path and path.is_file():
            pix = QPixmap(str(path))
            if not pix.isNull():
                self.cover_label.setPixmap(
                    pix.scaled(
                        140,
                        140,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.cover_label.setText("")

    def _apply_selected_alt(self) -> None:
        if not self._sheet or not self._candidates:
            return
        row = self.list_alts.currentRow()
        if row < 0 or row >= len(self._candidates):
            return
        cand = self._candidates[row]
        cover = fetch_cover_art_info(cand.release_id)
        if self._sheet.approval == ApprovalState.APPROVED:
            revoke_approval(
                self._sheet,
                note="Édition modifiée — réapprobation requise.",
            )
            self._approved_fp = None
        apply_release_candidate(self._sheet, cand, cover=cover, user_selected=True)
        self._enrichment_report = build_enrichment_report(
            cand,
            toc_durations_ms=(
                self._sheet.identity.toc.track_durations_ms
                if self._sheet.identity.toc is not None
                else None
            ),
        )
        self._fill_identify_ui(cover, None)
        self.lbl_id_status.setText(f"Édition appliquée : {cand.country or '?'} {cand.year or ''}")
        # Si W3 a déjà été peuplé, resynchroniser pour ne pas garder l’édition précédente
        if self._stack.currentIndex() == 2:
            self._refresh_w3()


    # --- W3 ---
    def _build_w3(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        form = QFormLayout()
        self.edit_artist = QLineEdit()
        self.edit_album = QLineEdit()
        self.spin_year = QSpinBox()
        self.spin_year.setRange(0, 2100)
        self.spin_year.setSpecialValueText("(aucune)")
        self.chk_year_unavailable = QCheckBox("Année de cette édition inconnue")
        self.edit_year_unavailable_reason = QLineEdit()
        self.edit_year_unavailable_reason.setPlaceholderText(
            "Justifier pourquoi aucune année fiable n’est disponible"
        )
        self.chk_compilation = QCheckBox("Cet album est une compilation")
        self.chk_compilation.setTristate(True)
        self.edit_label = QLineEdit()
        self.edit_catalog = QLineEdit()
        self.edit_country = QLineEdit()
        self.spin_disc_number = QSpinBox()
        self.spin_disc_number.setRange(1, 99)
        self.spin_disc_number.setAccessibleName("Numéro du disque dans le coffret")
        self.spin_disc_total = QSpinBox()
        self.spin_disc_total.setRange(1, 99)
        self.spin_disc_total.setAccessibleName("Nombre total de disques du coffret")
        form.addRow("Artiste album *", self.edit_artist)
        form.addRow("Titre album *", self.edit_album)
        form.addRow("Année", self.spin_year)
        form.addRow("", self.chk_year_unavailable)
        form.addRow("Justification", self.edit_year_unavailable_reason)
        form.addRow("", self.chk_compilation)
        form.addRow("Label", self.edit_label)
        form.addRow("N° catalogue", self.edit_catalog)
        form.addRow("Pays", self.edit_country)
        form.addRow("Disque dans le coffret", self.spin_disc_number)
        form.addRow("Nombre de disques", self.spin_disc_total)
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

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "Titre", "Artiste", "ms"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self._on_sheet_edited)
        v.addWidget(self.table)

        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setMaximumHeight(90)
        v.addWidget(QLabel("Chemins dans la bibliothèque"))
        v.addWidget(self.txt_preview)
        self.lbl_val = QLabel("")
        self.lbl_val.setWordWrap(True)
        v.addWidget(self.lbl_val)
        self.lbl_approval = QLabel("État : —")
        v.addWidget(self.lbl_approval)
        self.txt_enrichment = QTextBrowser()
        self.txt_enrichment.setReadOnly(True)
        self.txt_enrichment.setOpenExternalLinks(True)
        self.txt_enrichment.setMaximumHeight(150)
        self.txt_enrichment.setAccessibleName("Propositions de sources externes")
        v.addWidget(self.txt_enrichment)

        row = QHBoxLayout()
        b_draft = QPushButton("Enregistrer brouillon")
        b_draft.clicked.connect(self._save_draft)
        b_approve = QPushButton("Approuver la fiche")
        b_approve.setProperty("primary", True)
        b_approve.clicked.connect(self._do_approve)
        row.addWidget(b_draft)
        row.addWidget(b_approve)
        v.addLayout(row)
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
                self.table.setItem(r, 3, QTableWidgetItem(str(t.duration_ms)))
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
        self._validate_ui()
        if self._enrichment_report is not None:
            self.txt_enrichment.setHtml(self._enrichment_report.to_html())
        else:
            self.txt_enrichment.setPlainText(
                "Aucune proposition de source externe pour cette fiche."
            )

    def _on_year_unavailable_toggled(self, unavailable: bool) -> None:
        self.spin_year.setEnabled(not unavailable)
        self.edit_year_unavailable_reason.setEnabled(unavailable)
        self._on_sheet_edited()

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
            dur = int(self.table.item(row, 3).text()) if self.table.item(row, 3) else 0
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
        if self._stack.currentIndex() != 2:
            return
        self._apply_form_to_sheet()
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
        self.txt_preview.setPlainText("\n".join(self._sheet.path_preview))
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
        self.lbl_val.setText("\n".join(lines) if lines else "Validation OK.")
        self.lbl_approval.setText(f"État : {self._sheet.approval.value}")

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

    def _advise_duplicates_on_disc_read(self, disc_id: str) -> None:
        """Gate 1 : bandeau non bloquant (pas de modal — démarrage app fluide)."""
        assessment = assess_duplicates(self._db, disc_id=disc_id)
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
        return False

    def _do_approve(self) -> None:
        if not self._sheet:
            return
        self._apply_form_to_sheet()
        self._validate_ui()
        try:
            approve_sheet(self._sheet, note="UI wizard Approuver")
        except ApprovalError as exc:
            QMessageBox.warning(self, "Approbation refusée", str(exc))
            self._validate_ui()
            return
        # Gate 2 — après approbation : bandeau + message court
        assessment = assess_from_sheet(self._db, self._sheet)
        self._approved_fp = compute_approval_fingerprint(self._sheet)
        self._repo.save(self._sheet)
        self.lbl_approval.setText("État : Approved")
        if assessment.gate == DuplicateGate.ALLOW:
            QMessageBox.information(
                self,
                "Approuvé",
                "Fiche approuvée. Vous pouvez continuer vers l’extraction.",
            )
        elif assessment.gate == DuplicateGate.DENY:
            QMessageBox.warning(
                self,
                "Approuvé — opération concurrente",
                "Fiche approuvée, mais "
                + format_assessment_for_user(assessment),
            )
        else:
            # Inline sur W3 via lbl_val déjà affiché ; info courte
            QMessageBox.information(
                self,
                "Approuvé",
                "Fiche approuvée.\n\n"
                + assessment.summary_fr
                + "\n\nÀ l’extraction, l’action principale sera "
                "« Ouvrir l’album existant ». Le réarchivage restera secondaire.",
            )

    def _refresh_w4_preview(self) -> None:
        if not self._sheet:
            return
        ed = self._sheet.edition
        self.lbl_w4_recap.setText(
            f"{ed.album_artist} — {ed.album_title} "
            f"({ed.year or '?'}, {ed.country or '?'})\n"
            "Mode : archivage CD normal\n"
            f"Destination bibliothèque : {self._config.library_root}"
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
        self.lbl_progress = QLabel("En attente du lancement…")
        self.lbl_progress.setWordWrap(True)
        self.lbl_progress.setStyleSheet("font-size:15px;font-weight:600;color:#F1B65C;")
        self.lbl_progress.setAccessibleName("Message de progression")
        lv.addWidget(self.lbl_progress)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("Barre de progression")
        lv.addWidget(self.progress)
        note = QLabel("La barre suit les événements réels — aucun pourcentage inventé.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        lv.addWidget(note)
        steps_lbl = QLabel("Sous-étapes")
        steps_lbl.setObjectName("muted")
        lv.addWidget(steps_lbl)
        self.list_progress_steps = QListWidget()
        self.list_progress_steps.setObjectName("progressSteps")
        self.list_progress_steps.setAccessibleName("Sous-étapes d’archivage")
        self.list_progress_steps.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_progress_steps.setMaximumHeight(160)
        for name in PIPELINE_STEPS[:-1]:
            self.list_progress_steps.addItem(name)
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
        opt = QLabel("Si l’album existe déjà")
        opt.setObjectName("cardTitle")
        rv.addWidget(opt)
        self.radio_rename = QRadioButton("Créer un nouveau dossier (import-2, …)")
        self.radio_skip = QRadioButton("Ne pas publier si l’album existe déjà")
        self.radio_replace = QRadioButton(
            "Remplacer — l’ancien dossier ira dans une corbeille locale"
        )
        self.radio_replace.setEnabled(False)
        self.radio_replace.setToolTip(
            "Remplacement désactivé tant qu’une confirmation explicite n’est pas implémentée. "
            "Utilisez « Créer un nouveau dossier »."
        )
        self.radio_rename.setChecked(True)
        self._collision_group = QButtonGroup(self)
        for r in (self.radio_rename, self.radio_skip, self.radio_replace):
            self._collision_group.addButton(r)
            rv.addWidget(r)
        note_replace = QLabel(
            "Remplacer reste indisponible (préférez un nouveau dossier)."
        )
        note_replace.setWordWrap(True)
        note_replace.setObjectName("muted")
        rv.addWidget(note_replace)
        self.chk_publish = QCheckBox("Publier dans ma bibliothèque après extraction")
        self.chk_publish.setChecked(True)
        self.chk_publish.setAccessibleName("Publier dans ma bibliothèque")
        rv.addWidget(self.chk_publish)
        rv.addStretch(1)

        body.addWidget(left, 3)
        body.addWidget(right, 2)
        outer.addLayout(body, 1)
        return w

    def _collision_policy(self) -> CollisionPolicy:
        if self.radio_skip.isChecked():
            return CollisionPolicy.SKIP
        # Replace volontairement inaccessible sans confirmation UI (AVM-06C)
        if self.radio_replace.isChecked() and self.radio_replace.isEnabled():
            return CollisionPolicy.REPLACE
        return CollisionPolicy.RENAME

    def _start_archive(self) -> None:
        if not self._sheet:
            return
        try:
            assert_can_start_archive_rip(self._sheet)
        except ApprovalError as exc:
            QMessageBox.warning(self, "Archive bloquée", str(exc))
            return
        if not self.chk_publish.isChecked():
            QMessageBox.warning(
                self,
                "Publication",
                "Cochez « Publier dans ma bibliothèque » pour terminer l’archivage. "
                "(UI-1 n’offre pas de reprise de publication séparée.)",
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
            f"Destination bibliothèque : {self._config.library_root}"
        )
        self.lbl_w4_recap.setToolTip(self._config.library_root)
        self._set_busy(True)
        self.btn_cancel.setEnabled(True)
        self.progress.setValue(0)
        self.lbl_progress.setText("Démarrage…")
        self._highlight_progress_step(-1)

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
        thread = attach_worker_thread(
            worker,
            on_finished=self._on_archive_finished,
            on_failed=self._on_archive_failed,
            on_cleared=self._clear_thread,
            progress_slot=self._on_archive_progress,
        )
        self._thread = thread
        self._worker = worker
        thread.start()

    def _cancel_archive(self) -> None:
        if self._worker is not None and hasattr(self._worker, "cancel"):
            self._worker.cancel()
            self.lbl_progress.setText("Annulation…")

    def shutdown_background_work(self, *, timeout_ms: int = 12_000) -> bool:
        """Annule et attend le worker identify/archive (fermeture fenêtre)."""
        if not self.dvd.shutdown_background_work(timeout_ms=timeout_ms):
            return False
        ok = shutdown_worker_thread(self._thread, self._worker, timeout_ms=timeout_ms)
        if ok:
            self._clear_thread()
            self._set_busy(False)
        return ok

    def _highlight_progress_step(self, index: int) -> None:
        for i in range(self.list_progress_steps.count()):
            item = self.list_progress_steps.item(i)
            font = item.font()
            font.setBold(i == index)
            item.setFont(font)
            if i == index:
                item.setForeground(Qt.GlobalColor.darkGreen)
                self.list_progress_steps.setCurrentRow(i)
            elif i < index:
                item.setForeground(Qt.GlobalColor.darkGreen)
            else:
                item.setForeground(Qt.GlobalColor.gray)

    def _track_titles_for_progress(self) -> list[str]:
        if not self._sheet:
            return []
        return [
            (t.title or "").strip()
            for t in sorted(self._sheet.tracks, key=lambda x: x.number)
        ]

    def _on_archive_progress(self, message: str, fraction: object) -> None:
        titles = self._track_titles_for_progress()
        label = map_progress_message(
            str(message),
            track_titles=titles,
            track_total=len(titles) or None,
        )
        self.lbl_progress.setText(label)
        idx = progress_step_index(str(message), track_titles=titles)
        if idx >= 0:
            # PIPELINE_STEPS inclut « Terminé » ; la liste W4 l’exclut
            self._highlight_progress_step(min(idx, self.list_progress_steps.count() - 1))
        # Ne jamais inventer un % : n’avancer la barre que si fre:ac / pipeline fournit une fraction.
        if isinstance(fraction, (float, int)):
            self.progress.setValue(int(max(0.0, min(1.0, float(fraction))) * 100))

    def _on_archive_failed(self, message: str) -> None:
        self._set_busy(False)
        self.btn_cancel.setEnabled(False)
        self._last_report = None
        self.lbl_done.setProperty("role", "error")
        self.lbl_done.setText(f"Échec : {message}")
        self.txt_done.setPlainText(message)
        self._set_step(4)

    def _on_archive_finished(self, report: object) -> None:
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
        else:
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
        self.progress.setValue(100 if published else self.progress.value())
        self._set_step(4)

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
        self._disc_read = None
        self._sheet = None
        self._lookup = None
        self._candidates = []
        self._approved_fp = None
        self._advisory_warnings = []
        self._confirmed_rearchive = False
        self._last_report = None
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
        if self._stack.currentIndex() != 4:
            self.btn_next.setEnabled(not busy)

    def _clear_thread(self) -> None:
        self._thread = None
        self._worker = None
