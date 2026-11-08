"""Section Paramètres — test technique uniquement dans Avancé (A4)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.config import AppConfig, save_config
from audio_video_manager.extraction.cd import probe_freaccmd
from audio_video_manager.paths import ensure_app_dirs
from audio_video_manager.ui.path_labels import path_tooltip


class SettingsPage(QWidget):
    config_saved = Signal(object)
    start_technical_test = Signal()

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setAccessibleName("Paramètres — défilement")

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)

        title = QLabel("Paramètres")
        title.setObjectName("pageTitle")
        title.setAccessibleName("Paramètres")
        root.addWidget(title)

        root.addWidget(self._build_library())
        root.addWidget(self._build_identify())
        root.addWidget(self._build_extract())
        root.addWidget(self._build_advanced())

        save = QPushButton("Enregistrer")
        save.setProperty("primary", True)
        save.setAccessibleName("Enregistrer les paramètres")
        save.clicked.connect(self._save)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(save)
        root.addLayout(row)
        root.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

    def set_config(self, config: AppConfig) -> None:
        self._config = config
        self.edit_library.setText(config.library_root)
        self.edit_library.setToolTip(path_tooltip(config.library_root))
        mode = (config.library_ui_mode or "widgets").strip().lower()
        self.combo_lib_ui.setCurrentIndex(0 if mode == "qml" else 1)
        self.edit_freaccmd.setText(config.freaccmd_path)
        self.edit_freaccmd.setToolTip(path_tooltip(config.freaccmd_path))
        self.edit_ffmpeg.setText(config.ffmpeg_path)
        self.edit_ffmpeg.setToolTip(path_tooltip(config.ffmpeg_path))
        self.edit_dvdnav.setText(config.dvdnav_library_dir)
        self.edit_dvdnav.setToolTip(path_tooltip(config.dvdnav_library_dir))
        self.edit_jobs.setText(config.jobs_dir)
        self.edit_jobs.setToolTip(path_tooltip(config.jobs_dir))
        self.edit_logs.setText(config.log_dir)
        self.edit_logs.setToolTip(path_tooltip(config.log_dir))
        self.spin_flac.setValue(int(config.flac_compression))
        self.chk_eject.setChecked(bool(config.eject_after_rip))
        self.edit_pref.setText(config.preferred_release_country or "CA")

    def _path_row(self, edit: QLineEdit, browse: QPushButton) -> QWidget:
        from PySide6.QtWidgets import QSizePolicy

        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        edit.setMinimumWidth(0)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(edit, 1)
        browse.setFixedWidth(36)
        browse.setMinimumHeight(32)
        row.addWidget(browse)
        return wrap

    def _build_library(self) -> QGroupBox:
        box = QGroupBox("Bibliothèque")
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.edit_library = QLineEdit(self._config.library_root)
        self.edit_library.setToolTip(path_tooltip(self._config.library_root))
        browse = QPushButton("…")
        browse.setAccessibleName("Parcourir le dossier bibliothèque")
        browse.clicked.connect(self._browse_lib)
        form.addRow("Destination des albums :", self._path_row(self.edit_library, browse))
        library_hint = QLabel(
            "Les albums CD archivés seront publiés ici. Les fichiers de travail restent dans le dossier temporaire."
        )
        library_hint.setWordWrap(True)
        library_hint.setProperty("role", "muted")
        form.addRow(library_hint)
        self.combo_lib_ui = QComboBox()
        self.combo_lib_ui.addItem("Interface moderne (QML)", "qml")
        self.combo_lib_ui.addItem("Interface classique (Widgets)", "widgets")
        mode = (self._config.library_ui_mode or "widgets").strip().lower()
        self.combo_lib_ui.setCurrentIndex(0 if mode == "qml" else 1)
        self.combo_lib_ui.setAccessibleName("Mode d’affichage de la bibliothèque")
        form.addRow("Affichage :", self.combo_lib_ui)
        hint = QLabel(
            "Le basculement immédiat est aussi disponible dans Ma bibliothèque. "
            "Redémarrer l’app applique le choix enregistré."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        form.addRow(hint)
        return box

    def _build_identify(self) -> QGroupBox:
        box = QGroupBox("Identification")
        form = QFormLayout(box)
        self.edit_pref = QLineEdit(self._config.preferred_release_country or "CA")
        self.edit_pref.setMaxLength(2)
        self.edit_pref.setMaximumWidth(80)
        form.addRow("Pays préféré (départage) :", self.edit_pref)
        note = QLabel(
            "Ce réglage tranche entre éditions semblables ; "
            "ce n’est pas une preuve du pays de pressage."
        )
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        form.addRow(note)
        return box

    def _build_extract(self) -> QGroupBox:
        box = QGroupBox("Extraction")
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.edit_freaccmd = QLineEdit(self._config.freaccmd_path)
        self.edit_freaccmd.setToolTip(path_tooltip(self._config.freaccmd_path))
        browse = QPushButton("…")
        browse.setAccessibleName("Parcourir l’outil d’extraction")
        browse.clicked.connect(self._browse_freac)
        form.addRow("Outil d’extraction :", self._path_row(self.edit_freaccmd, browse))
        hint = QLabel("Logiciel fre:ac (freaccmd) — chemin configurable.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        form.addRow(hint)
        self.edit_ffmpeg = QLineEdit(self._config.ffmpeg_path)
        self.edit_ffmpeg.setToolTip(path_tooltip(self._config.ffmpeg_path))
        ffmpeg_browse = QPushButton("…")
        ffmpeg_browse.setAccessibleName("Parcourir ffmpeg pour DVD-Video")
        ffmpeg_browse.clicked.connect(self._browse_ffmpeg)
        form.addRow("FFmpeg DVD-Video :", self._path_row(self.edit_ffmpeg, ffmpeg_browse))
        self.edit_dvdnav = QLineEdit(self._config.dvdnav_library_dir)
        self.edit_dvdnav.setToolTip(path_tooltip(self._config.dvdnav_library_dir))
        dvdnav_browse = QPushButton("…")
        dvdnav_browse.setAccessibleName("Parcourir les DLL libdvdnav/libdvdread")
        dvdnav_browse.clicked.connect(self._browse_dvdnav)
        form.addRow("Bibliothèques DVD :", self._path_row(self.edit_dvdnav, dvdnav_browse))
        dvd_hint = QLabel(
            "Utilisez un build FFmpeg avec dvdvideo et des DLL libdvdnav/libdvdread "
            "CSS-off. Aucun déchiffrement n’est pris en charge."
        )
        dvd_hint.setWordWrap(True)
        dvd_hint.setProperty("role", "muted")
        form.addRow(dvd_hint)
        self.spin_flac = QSpinBox()
        self.spin_flac.setRange(0, 8)
        self.spin_flac.setValue(int(self._config.flac_compression))
        form.addRow("Compression FLAC :", self.spin_flac)
        self.chk_eject = QCheckBox("Éjecter après extraction")
        self.chk_eject.setChecked(bool(self._config.eject_after_rip))
        form.addRow("", self.chk_eject)
        return box

    def _build_advanced(self) -> QGroupBox:
        box = QGroupBox("Avancé")
        form = QFormLayout(box)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.edit_jobs = QLineEdit(self._config.jobs_dir)
        self.edit_jobs.setToolTip(path_tooltip(self._config.jobs_dir))
        self.edit_logs = QLineEdit(self._config.log_dir)
        self.edit_logs.setToolTip(path_tooltip(self._config.log_dir))
        form.addRow("Dossier temporaire :", self.edit_jobs)
        form.addRow("Dossier logs :", self.edit_logs)

        chk = QCheckBox("Auto-approuver si haute confiance — non disponible")
        chk.setChecked(False)
        chk.setEnabled(False)
        form.addRow(chk)

        dvd = QLabel("DVD-Video : choisissez ce type de disque dans Archiver.")
        dvd.setProperty("role", "muted")
        dvd.setWordWrap(True)
        form.addRow(dvd)

        tech = QPushButton("Lancer un test technique (zone temporaire uniquement)…")
        tech.setMinimumHeight(36)
        tech.clicked.connect(self._confirm_tech)
        form.addRow(tech)

        probe_btn = QPushButton("Vérifier l’outil d’extraction (diagnostic)")
        probe_btn.setMinimumHeight(36)
        probe_btn.clicked.connect(self._probe)
        form.addRow(probe_btn)
        self.lbl_probe = QLabel("")
        self.lbl_probe.setWordWrap(True)
        self.lbl_probe.setProperty("role", "muted")
        form.addRow(self.lbl_probe)
        return box

    def _browse_lib(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Dossier bibliothèque", self.edit_library.text()
        )
        if path:
            self.edit_library.setText(path)
            self.edit_library.setToolTip(path)

    def _browse_freac(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "freaccmd.exe",
            self.edit_freaccmd.text() or r"C:\Program Files\freac",
            "Exécutables (*.exe);;Tous (*.*)",
        )
        if path:
            self.edit_freaccmd.setText(path)
            self.edit_freaccmd.setToolTip(path)

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "ffmpeg.exe",
            self.edit_ffmpeg.text() or str(Path.home()),
            "Exécutables (*.exe);;Tous (*.*)",
        )
        if path:
            self.edit_ffmpeg.setText(path)
            self.edit_ffmpeg.setToolTip(path)

    def _browse_dvdnav(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Dossier contenant libdvdnav-4.dll et libdvdread-8.dll",
            self.edit_dvdnav.text() or str(Path.home()),
        )
        if path:
            self.edit_dvdnav.setText(path)
            self.edit_dvdnav.setToolTip(path)

    def _read(self) -> AppConfig:
        c = self._config
        c.library_root = self.edit_library.text().strip()
        c.freaccmd_path = self.edit_freaccmd.text().strip()
        c.ffmpeg_path = self.edit_ffmpeg.text().strip()
        c.dvdnav_library_dir = self.edit_dvdnav.text().strip()
        c.jobs_dir = self.edit_jobs.text().strip()
        c.log_dir = self.edit_logs.text().strip()
        c.flac_compression = int(self.spin_flac.value())
        c.eject_after_rip = self.chk_eject.isChecked()
        pref = (self.edit_pref.text() or "CA").strip().upper()
        c.preferred_release_country = pref or "CA"
        c.auto_approve_high_confidence = False
        c.library_ui_mode = self.combo_lib_ui.currentData() or "widgets"
        return c

    def _save(self) -> None:
        cfg = self._read()
        ensure_app_dirs(
            jobs_dir=Path(cfg.jobs_dir) if cfg.jobs_dir else None,
            log_dir=Path(cfg.log_dir) if cfg.log_dir else None,
        )
        path = save_config(cfg)
        self.config_saved.emit(cfg)
        QMessageBox.information(self, "Paramètres", f"Enregistrés.\n{path}")

    def _confirm_tech(self) -> None:
        r = QMessageBox.question(
            self,
            "Test technique",
            (
                "MODE TEST TECHNIQUE\n\n"
                "• Extraction uniquement dans le dossier temporaire\n"
                "• Aucune publication dans la bibliothèque\n"
                "• Confirmation requise\n\n"
                "Continuer ?"
            ),
        )
        if r == QMessageBox.StandardButton.Yes:
            self._save()
            self.start_technical_test.emit()

    def _probe(self) -> None:
        cfg = self._read()
        st = probe_freaccmd(
            configured_path=cfg.freaccmd_path or None,
            freac_install_dir=cfg.freac_install_dir or None,
            run_probes=False,
        )
        if st.found:
            self.lbl_probe.setText(f"OK — {st.path}")
        else:
            self.lbl_probe.setText("Introuvable — vérifiez le chemin.")
