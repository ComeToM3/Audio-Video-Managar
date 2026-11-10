"""Coquille AVM-08E — Brume pastel, barre latérale + fond peinture."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager import __version__
from audio_video_manager.config import AppConfig, load_config
from audio_video_manager.extraction.cd import probe_freaccmd
from audio_video_manager.logging_setup import get_logger, setup_logging
from audio_video_manager.metadata.enums import JobMode
from audio_video_manager.orchestration.reconciliation import (
    LivenessKind,
    reconcile_unfinished_jobs,
)
from audio_video_manager.orchestration.rip_job import RipJobReport
from audio_video_manager.paths import ensure_app_dirs
from audio_video_manager.storage import Database
from audio_video_manager.ui.assets_paths import paint_canvas_path
from audio_video_manager.ui.rip_worker import RipWorker
from audio_video_manager.ui.sections.history_page import HistoryPage
from audio_video_manager.ui.sections.library_host import LibraryHost
from audio_video_manager.ui.sections.settings_page import SettingsPage
from audio_video_manager.ui.theme import apply_app_style
from audio_video_manager.ui.thread_lifecycle import (
    attach_worker_thread,
    shutdown_worker_thread,
)
from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage

log = get_logger("ui")

_WM_DEVICECHANGE = 0x0219
_DBT_DEVICEARRIVAL = 0x8000
_DBT_DEVICEREMOVECOMPLETE = 0x8004
_DBT_DEVTYP_VOLUME = 0x00000002


def _is_volume_device_change(message: int, event: int, device_type: int) -> bool:
    return (
        message == _WM_DEVICECHANGE
        and event in {_DBT_DEVICEARRIVAL, _DBT_DEVICEREMOVECOMPLETE}
        and device_type == _DBT_DEVTYP_VOLUME
    )

# Ordre stack / API tests (inchangé)
NAV_LABELS = (
    "Archiver un disque",
    "Ma bibliothèque",
    "Historique",
    "Paramètres",
)
# Ordre visuel barre latérale : Bibliothèque, Archiver, Historique, Paramètres
SIDEBAR_ITEMS: tuple[tuple[int, str, str], ...] = (
    (1, "Bibliothèque", "Bibl."),
    (0, "Archiver", "Arch."),
    (2, "Historique", "Histo."),
    (3, "Paramètres", "Régl."),
)
NAV_ARCHIVE = 0
NARROW_BREAKPOINT = 900
SIDE_WIDE = 196
SIDE_NARROW = 76


class AtelierRoot(QWidget):
    """Racine peinte : toile Brume pastel (nappes fluides, sans aplat noir)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("centralRoot")
        self._pix = QPixmap()
        path = paint_canvas_path()
        if path.is_file():
            self._pix = QPixmap(str(path))

    def paintEvent(self, event) -> None:  # noqa: N802, ARG002
        from PySide6.QtGui import QColor

        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#F0EBE3"))
        if not self._pix.isNull():
            scaled = self._pix.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            p.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig, db: Database) -> None:
        super().__init__()
        self._config = config
        self._db = db
        self._tech_thread: QThread | None = None
        self._tech_worker: RipWorker | None = None
        self._narrow = False
        self._side_buttons: dict[int, QPushButton] = {}
        # Compat tests 08D (alias)
        self._pill_buttons: list[QPushButton] = []
        self._startup_reconcile_done = False

        self.setWindowTitle(f"AudioVideo Manager {__version__}")
        self.resize(1100, 720)
        self.setMinimumSize(720, 560)

        central = AtelierRoot()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # --- Rail gauche ---
        self._side = QWidget()
        self._side.setObjectName("sideRail")
        self._side.setAccessibleName("Navigation principale")
        self._side.setFixedWidth(SIDE_WIDE)
        side_lay = QVBoxLayout(self._side)
        side_lay.setContentsMargins(12, 16, 12, 16)
        side_lay.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(0)
        self._brand_a = QLabel("AudioVideo ")
        self._brand_a.setObjectName("brandMark")
        self._brand_a.setAccessibleName("AudioVideo Manager")
        self._brand_b = QLabel("Manager")
        self._brand_b.setObjectName("brandAccent")
        brand_row.addWidget(self._brand_a)
        brand_row.addWidget(self._brand_b)
        brand_row.addStretch(1)
        side_lay.addLayout(brand_row)
        self._brand_sub = QLabel("Collection locale")
        self._brand_sub.setObjectName("sideBrandSub")
        side_lay.addWidget(self._brand_sub)
        side_lay.addSpacing(12)

        for stack_idx, label, _short in SIDEBAR_ITEMS:
            btn = QPushButton(label)
            btn.setObjectName("sideNavBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("active", "true" if stack_idx == NAV_ARCHIVE else "false")
            btn.setAccessibleName(NAV_LABELS[stack_idx])
            btn.clicked.connect(lambda _c=False, r=stack_idx: self._on_nav(r))
            side_lay.addWidget(btn)
            self._side_buttons[stack_idx] = btn
            self._pill_buttons.append(btn)

        side_lay.addStretch(1)
        self.lbl_reader = QLabel("Lecteur : —")
        self.lbl_reader.setProperty("role", "muted")
        self.lbl_reader.setWordWrap(True)
        tagline = QLabel("Sans cloud")
        tagline.setProperty("role", "muted")
        side_lay.addWidget(self.lbl_reader)
        side_lay.addWidget(tagline)
        root.addWidget(self._side)

        # --- Colonne contenu ---
        content = QWidget()
        content.setObjectName("contentStage")
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(18, 16, 18, 16)
        content_lay.setSpacing(10)

        # Shims API tests
        self.tab_bar = QTabBar()
        self.tab_bar.setObjectName("navTabs")
        for label in NAV_LABELS:
            self.tab_bar.addTab(label)
        self.tab_bar.setVisible(False)
        self.tab_bar.setMaximumHeight(0)
        self.tab_bar.currentChanged.connect(self._on_nav)
        content_lay.addWidget(self.tab_bar)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setAccessibleName("Navigation principale (compat)")
        for label in NAV_LABELS:
            item = QListWidgetItem(label, self.nav)
            item.setData(Qt.ItemDataRole.AccessibleTextRole, label)
        self.nav.setCurrentRow(NAV_ARCHIVE)
        self.nav.currentRowChanged.connect(self._on_nav)
        self.nav.setVisible(False)
        self.nav.setMaximumHeight(0)
        content_lay.addWidget(self.nav)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.wizard = ArchiveWizardPage(config, db)
        self.wizard.status_message.connect(self._on_status)
        self.wizard.archive_busy_changed.connect(self._on_busy)
        self.wizard.archive_status_changed.connect(self._on_archive_status)
        self.wizard.request_navigate.connect(self.navigate_to)
        self.wizard.library_changed.connect(self._on_library_changed)
        self.wizard.open_video_library.connect(self._open_video_library)
        self.page_library = LibraryHost(config, db)
        self.page_library.busy_changed.connect(self._on_busy)
        self.page_history = HistoryPage(
            db,
            config=config,
            on_busy=self._on_busy,
            on_library_changed=self._on_library_changed,
        )
        self.page_settings = SettingsPage(config)
        self.page_settings.config_saved.connect(self._on_config_saved)
        self.page_settings.start_technical_test.connect(self._start_technical_test)

        self.stack.addWidget(self.wizard)
        self.stack.addWidget(self.page_library)
        self.stack.addWidget(self.page_history)
        self.stack.addWidget(self.page_settings)
        content_lay.addWidget(self.stack, 1)
        root.addWidget(content, 1)

        self.archive_status_label = QLabel("")
        self.archive_status_label.setProperty("role", "muted")
        self.archive_status_label.setAccessibleName("État permanent de l’archivage CD")
        self.archive_status_progress = QProgressBar()
        self.archive_status_progress.setRange(0, 1)
        self.archive_status_progress.setTextVisible(False)
        self.archive_status_progress.setFixedWidth(170)
        self.archive_status_progress.setAccessibleName("Progression de l’archivage CD")
        self.statusBar().addWidget(self.archive_status_label, 1)
        self.statusBar().addPermanentWidget(self.archive_status_progress)
        self.archive_status_label.hide()
        self.archive_status_progress.hide()

        self._refresh_reader_status()
        self._sync_side_styles(NAV_ARCHIVE)

    def current_section(self) -> int:
        return self.stack.currentIndex()

    def navigate_to(self, row: int) -> None:
        self._on_nav(row)

    def _sync_side_styles(self, row: int) -> None:
        for idx, btn in self._side_buttons.items():
            btn.setProperty("active", "true" if idx == row else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _sync_nav_widgets(self, row: int) -> None:
        self.nav.blockSignals(True)
        self.tab_bar.blockSignals(True)
        self.nav.setCurrentRow(row)
        self.tab_bar.setCurrentIndex(row)
        self.nav.blockSignals(False)
        self.tab_bar.blockSignals(False)
        self._sync_side_styles(row)

    def _operation_busy(self) -> bool:
        return (
            self.wizard.is_busy()
            or self.wizard.is_media_scan_busy()
            or self._tech_thread is not None
            or self.page_history.is_recovery_busy()
            or self.page_library.is_busy()
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._startup_reconcile_done:
            self._startup_reconcile_done = True
            self._run_startup_reconciliation()

    def _run_startup_reconciliation(self) -> None:
        """Détecte jobs orphelins — jamais d’abandon automatique ni de purge fichiers."""
        try:
            report = reconcile_unfinished_jobs(self._db)
        except Exception as exc:  # noqa: BLE001
            log.warning("Réconciliation démarrage échouée : %s", exc)
            return
        if report.scanned == 0:
            return
        lines: list[str] = []
        if report.changed_count:
            lines.append(
                f"{report.changed_count} opération(s) marquées « Interrompues » "
                "(aucune extraction active confirmée). Fichiers intacts."
            )
        uncertain = [
            a
            for a in report.actions
            if a.liveness == LivenessKind.UNCERTAIN
        ]
        active = [
            a
            for a in report.actions
            if a.liveness == LivenessKind.PROCESS_ACTIVE
        ]
        if active:
            lines.append(
                f"{len(active)} opération(s) encore liées à un processus actif — "
                "aucune modification d’état."
            )
        if uncertain:
            lines.append(
                f"{len(uncertain)} opération(s) en état incertain "
                "(fre:ac peut encore tourner) — non abandonnées automatiquement."
            )
        if not lines:
            return
        banner = "Réconciliation au démarrage : " + " ".join(lines)
        self.page_history.set_reconcile_banner(banner)
        self.page_history.refresh()
        QMessageBox.information(
            self,
            "Opérations interrompues",
            "\n\n".join(lines)
            + "\n\nOuvrez l’Historique pour abandonner (sans supprimer) "
            "ou reprendre depuis les fichiers lorsque c’est possible.",
        )

    def _on_nav(self, row: int) -> None:
        if row < 0:
            return
        if self.page_library.is_busy() and row != 1:
            self._sync_nav_widgets(1)
            return
        if self.page_history.is_recovery_busy() and row != 2:
            QMessageBox.information(
                self,
                "Récupération en cours",
                "Attendez la fin de la reprise depuis fichiers avant de changer de section.",
            )
            self._sync_nav_widgets(2)
            return
        if self._tech_thread is not None and row != 3:
            QMessageBox.information(
                self,
                "Test technique en cours",
                "Attendez la fin du test technique avant de changer de section.",
            )
            self._sync_nav_widgets(3)
            return
        if (
            self.wizard.is_busy()
            and not self.wizard.is_archive_active()
            and row != NAV_ARCHIVE
        ):
            QMessageBox.information(
                self,
                "Archivage en cours",
                "Attendez la fin de l’archivage ou annulez-le avant de changer de section.",
            )
            self._sync_nav_widgets(NAV_ARCHIVE)
            return
        self.stack.setCurrentIndex(row)
        self._sync_nav_widgets(row)
        self.stack.setFocus(Qt.FocusReason.OtherFocusReason)
        if row != NAV_ARCHIVE:
            self._refresh_reader_status()
        if row == 1:
            self.page_library.refresh()
        elif row == 2:
            self.page_history.refresh()
        elif row == NAV_ARCHIVE and not self.wizard.is_archive_active():
            self.wizard.schedule_optical_scan(auto_identify=True)

    def nativeEvent(self, event_type, message):  # noqa: N802
        if sys.platform != "win32":
            return False, 0
        try:
            event_name = bytes(event_type)
        except (TypeError, ValueError):
            return False, 0
        if event_name not in {b"windows_generic_MSG", b"windows_dispatcher_MSG"}:
            return False, 0

        try:
            import ctypes
            from ctypes import wintypes

            message_pointer = int(message)
            if not message_pointer:
                return False, 0
            native_message = ctypes.cast(
                message_pointer, ctypes.POINTER(wintypes.MSG)
            ).contents
            if (
                self.stack.currentIndex() == NAV_ARCHIVE
                and native_message.message == _WM_DEVICECHANGE
                and native_message.wParam
                in {_DBT_DEVICEARRIVAL, _DBT_DEVICEREMOVECOMPLETE}
                and native_message.lParam
            ):
                class DeviceBroadcastHeader(ctypes.Structure):
                    _fields_ = [
                        ("size", wintypes.DWORD),
                        ("device_type", wintypes.DWORD),
                        ("reserved", wintypes.DWORD),
                    ]

                header = DeviceBroadcastHeader.from_address(
                    int(native_message.lParam)
                )
                if (
                    header.size >= ctypes.sizeof(DeviceBroadcastHeader)
                    and _is_volume_device_change(
                        int(native_message.message),
                        int(native_message.wParam),
                        int(header.device_type),
                    )
                ):
                    self.wizard.schedule_optical_scan(auto_identify=True)
        except Exception as exc:  # noqa: BLE001
            log.debug("Notification optique Windows ignorée : %s", exc)
        return False, 0

    def _on_status(self, message: str) -> None:
        if self.stack.currentIndex() == NAV_ARCHIVE:
            self.lbl_reader.setText(message)

    def _on_archive_status(
        self, message: str, fraction: object, active: bool
    ) -> None:
        self.archive_status_label.setText(message)
        self.archive_status_label.setVisible(bool(message))
        try:
            measured = float(fraction)
        except (TypeError, ValueError):
            measured = -1.0
        if active and 0.0 <= measured <= 1.0:
            self.archive_status_progress.setRange(0, 100)
            self.archive_status_progress.setValue(round(measured * 100))
            self.archive_status_progress.setTextVisible(True)
            self.archive_status_progress.setFormat("fre:ac %p%")
            self.archive_status_progress.setToolTip(
                "Valeur rapportée par fre:ac; les autres étapes ne sont pas incluses."
            )
            self.archive_status_progress.show()
        elif active:
            self.archive_status_progress.setRange(0, 0)
            self.archive_status_progress.setTextVisible(False)
            self.archive_status_progress.setToolTip(
                "Progression chiffrée indisponible; activité en cours."
            )
            self.archive_status_progress.show()
        elif fraction is not None and measured == 1.0:
            self.archive_status_progress.setRange(0, 100)
            self.archive_status_progress.setValue(100)
            self.archive_status_progress.setTextVisible(True)
            self.archive_status_progress.setFormat("Archivé")
            self.archive_status_progress.show()
        else:
            self.archive_status_progress.hide()

    def _on_busy(self, busy: bool) -> None:
        archive_active = self.wizard.is_archive_active()
        locked = (
            (busy and not archive_active)
            or (self.wizard.is_busy() and not archive_active)
            or self._tech_thread is not None
            or self.page_history.is_recovery_busy()
            or self.page_library.is_busy()
        )
        self.nav.setEnabled(not locked)
        self.tab_bar.setEnabled(not locked)
        for btn in self._side_buttons.values():
            btn.setEnabled(not locked)
    def closeEvent(self, event) -> None:  # noqa: N802
        if self._operation_busy():
            reply = QMessageBox.question(
                self,
                "Opération en cours",
                "Une détection de disque, extraction, identification ou récupération est en cours.\n"
                "Voulez-vous l’annuler et quitter ?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            ok_tech = shutdown_worker_thread(self._tech_thread, self._tech_worker)
            ok_wiz = self.wizard.shutdown_background_work()
            ok_hist = self.page_history.shutdown_background_work()
            ok_lib = self.page_library.shutdown_background_work()
            if not (ok_tech and ok_wiz and ok_hist and ok_lib):
                QMessageBox.warning(
                    self,
                    "Arrêt incomplet",
                    "Le thread d’arrière-plan ne s’est pas arrêté à temps. "
                    "Réessayez dans quelques secondes.",
                )
                event.ignore()
                return
            self._tech_thread = None
            self._tech_worker = None
        event.accept()

    def _on_library_changed(self) -> None:
        self.page_library.refresh()

    def _open_video_library(self) -> None:
        if self._operation_busy():
            return
        self.page_library.media_tabs.setCurrentIndex(1)
        self.navigate_to(1)

    def _on_config_saved(self, config: AppConfig) -> None:
        self._config = config
        self.wizard.set_config(config)
        self.page_library.set_config(config)
        self._refresh_reader_status()

    def _refresh_reader_status(self) -> None:
        st = probe_freaccmd(
            configured_path=self._config.freaccmd_path or None,
            freac_install_dir=self._config.freac_install_dir or None,
            run_probes=False,
        )
        if st.found:
            self.lbl_reader.setText("Outil d’extraction détecté")
        else:
            self.lbl_reader.setText("Outil manquant — Paramètres")

    def _start_technical_test(self) -> None:
        if self.wizard.is_busy() or self._tech_thread is not None:
            QMessageBox.warning(self, "Occupé", "Une opération est déjà en cours.")
            return
        st = probe_freaccmd(
            configured_path=self._config.freaccmd_path or None,
            freac_install_dir=self._config.freac_install_dir or None,
            run_probes=False,
        )
        if not st.found or not st.path:
            QMessageBox.warning(
                self,
                "Test technique",
                "L’outil d’extraction est introuvable. Vérifiez Paramètres.",
            )
            return
        self.wizard.refresh_drives()
        drives = self.wizard.available_drives()
        if not drives:
            QMessageBox.warning(self, "Test technique", "Aucun lecteur CD détecté.")
            return
        drive_number = drives[0].number
        jobs_root = Path(self._config.jobs_dir)
        jobs_root.mkdir(parents=True, exist_ok=True)
        worker = RipWorker(
            freaccmd=st.path,
            jobs_root=jobs_root,
            drive_number=int(drive_number),
            db_path=self._db.path,
            flac_compression=self._config.flac_compression,
            eject_after_rip=False,
            mode=JobMode.TECHNICAL_TEST,
            metadata=None,
        )
        thread = attach_worker_thread(
            worker,
            on_finished=self._on_tech_finished,
            on_failed=self._on_tech_failed,
            on_cleared=self._clear_tech,
        )
        self._tech_worker = worker
        self._tech_thread = thread
        self._on_busy(True)
        thread.start()
        self.lbl_reader.setText("Test technique en cours…")
        QMessageBox.information(
            self,
            "Test technique",
            "Extraction de test démarrée (zone temporaire uniquement).\n"
            "Ne fermez pas l’application avant la fin ou l’annulation.",
        )

    def _on_tech_finished(self, report: object) -> None:
        assert isinstance(report, RipJobReport)
        non_publish = (
            "Mode : test technique (technical_test)\n"
            "Publication bibliothèque : aucune; les fichiers restent dans le dossier temporaire.\n"
        )
        if report.rip.success:
            msg = (
                non_publish
                + f"Test terminé : {len(report.rip.flac_files)} fichier(s) audio.\n"
                + f"Dossier temporaire : {report.workdir}"
            )
        else:
            msg = (
                non_publish
                + "Le test d’extraction n’a pas abouti. Consultez l’historique pour le détail."
            )
        QMessageBox.information(self, "Test technique", msg)
        self._refresh_reader_status()

    def _on_tech_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Test technique", message)
        self._refresh_reader_status()

    def _clear_tech(self) -> None:
        self._tech_thread = None
        self._tech_worker = None
        self._on_busy(self.wizard.is_busy())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        narrow = self.width() < NARROW_BREAKPOINT
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self.nav.setVisible(False)
        self.tab_bar.setVisible(False)
        self._side.setFixedWidth(SIDE_NARROW if narrow else SIDE_WIDE)
        if narrow:
            self._brand_a.setText("A")
            self._brand_b.setText("VM")
            self._brand_sub.setText("")
        else:
            self._brand_a.setText("AudioVideo ")
            self._brand_b.setText("Manager")
            self._brand_sub.setText("Collection locale")
        for stack_idx, label, short in SIDEBAR_ITEMS:
            btn = self._side_buttons[stack_idx]
            btn.setText(short if narrow else label)
            btn.setToolTip(label if narrow else "")


def run_app(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv
    config = load_config()
    ensure_app_dirs(
        jobs_dir=Path(config.jobs_dir) if config.jobs_dir else None,
        log_dir=Path(config.log_dir) if config.log_dir else None,
    )
    setup_logging(Path(config.log_dir) if config.log_dir else None)
    log.info(
        "AVM28E_TRACE startup executable=%s main_window=%s archive_wizard=%s "
        "ui=Widgets",
        sys.executable,
        Path(__file__).resolve(),
        Path(__file__).parent / "wizard" / "archive_wizard.py",
    )
    db = Database()
    db.initialize()

    app = QApplication(args)
    apply_app_style(app)
    window = MainWindow(config, db)
    window.show()
    code = app.exec()
    db.close()
    return int(code)
