"""Hôte Bibliothèque hybride — QML prioritaire, repli Widgets (AVM-08B)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.config import AppConfig
from audio_video_manager.logging_setup import get_logger
from audio_video_manager.storage.database import Database
from audio_video_manager.ui.sections.library_page import LibraryPage, VideoLibraryPage

log = get_logger("ui.library_host")

# Modes : qml | widgets
ENV_FORCE = "AVM_LIBRARY_UI"


def resolve_library_ui_mode(config: AppConfig) -> str:
    env = (os.environ.get(ENV_FORCE) or "").strip().lower()
    if env in {"qml", "widgets"}:
        return env
    mode = (getattr(config, "library_ui_mode", None) or "widgets").strip().lower()
    return mode if mode in {"qml", "widgets"} else "widgets"


class LibraryHost(QWidget):
    """
    Conteneur hybride.
    - Mode QML : QQuickWidget + bridge sur Database partagée
    - Mode Widgets : LibraryPage 06L (repli explicite)
    """

    busy_changed = Signal(bool)

    def __init__(self, config: AppConfig, db: Database, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._db = db
        self._qml_ok = False
        self._bridge = None
        self._quick = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(28, 8, 28, 0)
        self.lbl_mode = QLabel()
        self.lbl_mode.setProperty("role", "muted")
        self.btn_toggle = QPushButton()
        self.btn_toggle.setProperty("ghost", True)
        self.btn_toggle.setAccessibleName("Basculer l’interface bibliothèque")
        self.btn_toggle.clicked.connect(self._toggle_mode)
        bar.addWidget(self.lbl_mode)
        bar.addStretch(1)
        bar.addWidget(self.btn_toggle)
        root.addLayout(bar)

        self.media_tabs = QTabBar()
        self.media_tabs.addTab("Albums")
        self.media_tabs.addTab("Vidéos / audio DVD")
        self.media_tabs.setAccessibleName("Type de bibliothèque")
        root.addWidget(self.media_tabs)
        self._media_stack = QStackedWidget()
        root.addWidget(self._media_stack, 1)
        self._stack = QStackedWidget()
        self._media_stack.addWidget(self._stack)
        self.video_page = VideoLibraryPage(db, config)
        self.video_page.busy_changed.connect(self.busy_changed.emit)
        self._media_stack.addWidget(self.video_page)
        self.media_tabs.currentChanged.connect(self._media_stack.setCurrentIndex)

        # Widgets always available as fallback / test surface
        self.widgets_page = LibraryPage(config, db)
        self._stack.addWidget(self.widgets_page)

        self._qml_page = QWidget()
        qml_layout = QVBoxLayout(self._qml_page)
        qml_layout.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(self._qml_page)

        desired = resolve_library_ui_mode(config)
        if desired == "qml":
            if self._try_start_qml():
                self._show_qml()
            else:
                self._show_widgets(reason="QML indisponible — interface classique.")
        else:
            self._show_widgets()

    # --- API compatible LibraryPage (tests / main_window) ---
    @property
    def list(self):
        return self.widgets_page.list

    @property
    def search(self):
        return self.widgets_page.search

    @property
    def tbl_tracks(self):
        return self.widgets_page.tbl_tracks

    @property
    def btn_open_album(self):
        return self.widgets_page.btn_open_album

    @property
    def lbl_detail(self):
        return self.widgets_page.lbl_detail

    @property
    def using_qml(self) -> bool:
        return self._qml_ok and self._stack.currentWidget() is self._qml_page

    def set_config(self, config: AppConfig) -> None:
        self._config = config
        self.widgets_page.set_config(config)
        self.video_page.set_config(config)

    def refresh(self) -> None:
        self.widgets_page.refresh()
        self.video_page.refresh()
        if self._bridge is not None:
            self._bridge.refresh()
            self._sync_qml_selection()

    def is_busy(self) -> bool:
        return self.video_page.is_busy()

    def shutdown_background_work(self, *, timeout_ms: int = 12_000) -> bool:
        return self.video_page.shutdown_background_work(timeout_ms=timeout_ms)

    def _sync_qml_selection(self) -> None:
        if self._bridge is None or self._quick is None:
            return
        if self._bridge.albumCount() <= 0:
            return
        self._bridge.selectRow(0)
        root = self._quick.rootObject()
        if root is not None:
            root.setProperty("selectedRow", 0)
            fn = getattr(root, "reselectFirst", None)
            if callable(fn):
                fn()

    def _try_start_qml(self) -> bool:
        try:
            from PySide6.QtQuickWidgets import QQuickWidget

            from audio_video_manager.ui.qml.library_bridge import LibraryBridge

            qml_root = Path(__file__).resolve().parents[1] / "qml"
            main_qml = qml_root / "LibraryPage.qml"
            if not main_qml.is_file():
                log.warning("QML manquant: %s", main_qml)
                return False

            self._bridge = LibraryBridge(self._db, self)
            self._bridge.openFailed.connect(self._on_open_failed)

            quick = QQuickWidget()
            quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
            quick.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, False)
            quick.engine().addImportPath(str(qml_root))
            quick.rootContext().setContextProperty("library", self._bridge)
            from audio_video_manager.ui.assets_paths import paint_canvas_path

            canvas = paint_canvas_path()
            if canvas.is_file():
                quick.rootContext().setContextProperty(
                    "atelierBg", QUrl.fromLocalFile(str(canvas))
                )
            else:
                quick.rootContext().setContextProperty("atelierBg", QUrl())
            # Laisse entrevoir le chrome ; le QML peint aussi le canvas
            quick.setClearColor(Qt.GlobalColor.transparent)
            quick.setSource(QUrl.fromLocalFile(str(main_qml)))
            if quick.status() == QQuickWidget.Status.Error:
                errs = quick.errors()
                log.error("Erreur QML: %s", "; ".join(str(e) for e in errs))
                return False

            # Remplacer contenu page QML
            lay = self._qml_page.layout()
            assert isinstance(lay, QVBoxLayout)
            while lay.count():
                item = lay.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
            lay.addWidget(quick)
            self._quick = quick
            self._qml_ok = True
            log.info("Bibliothèque QML active")
            return True
        except Exception as exc:  # noqa: BLE001
            log.exception("Échec démarrage QML: %s", exc)
            self._qml_ok = False
            self._bridge = None
            self._quick = None
            return False

    def _show_qml(self) -> None:
        self._stack.setCurrentWidget(self._qml_page)
        self.lbl_mode.setText("Bibliothèque · interface moderne (QML)")
        self.btn_toggle.setText("Interface classique…")
        self.refresh()

    def _show_widgets(self, reason: str | None = None) -> None:
        self._stack.setCurrentWidget(self.widgets_page)
        self.lbl_mode.setText("Bibliothèque · interface classique (Widgets)")
        # Ne pas précharger QML ici (AVM-07A/08D) — chargement paresseux au basculement
        self.btn_toggle.setText("Interface moderne…")
        self.btn_toggle.setEnabled(True)
        self.widgets_page.refresh()
        if reason:
            log.info("%s", reason)

    def _toggle_mode(self) -> None:
        if self.using_qml:
            self._show_widgets()
            return
        if self._qml_ok or self._try_start_qml():
            self._show_qml()
        else:
            QMessageBox.warning(
                self,
                "Bibliothèque",
                "L’interface moderne (QML) n’a pas pu démarrer.\n"
                "L’interface classique reste disponible.",
            )

    def _on_open_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Dossier album", message)

    def force_widgets_fallback(self) -> None:
        """API tests / recovery."""
        self._show_widgets(reason="repli forcé")

    def shutdown_ui(self) -> None:
        """Teardown ordonné QQuickWidget / bridge (AVM-10C.1).

        Sans cela, les wrappers Shiboken survivent au ``close()`` Python et
        explosent au GC / finalizer (0xC0000005) — constat survivors audit.
        """
        quick = self._quick
        bridge = self._bridge
        self._quick = None
        self._bridge = None
        self._qml_ok = False
        if quick is not None:
            try:
                quick.setSource(QUrl())
            except RuntimeError:
                pass
            try:
                eng = quick.engine()
                eng.clearComponentCache()
            except RuntimeError:
                pass
            try:
                quick.setParent(None)
                quick.deleteLater()
            except RuntimeError:
                pass
        if bridge is not None:
            try:
                bridge.setParent(None)
                bridge.deleteLater()
            except RuntimeError:
                pass
