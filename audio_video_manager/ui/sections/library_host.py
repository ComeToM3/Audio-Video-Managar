"""Hôte Qt Widgets de la Bibliothèque."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from audio_video_manager.config import AppConfig
from audio_video_manager.storage.database import Database
from audio_video_manager.ui.sections.library_page import LibraryPage, VideoLibraryPage

class LibraryHost(QWidget):
    """Hôte Widgets de la Bibliothèque, vidéos/DVD et export Android."""

    busy_changed = Signal(bool)

    def __init__(self, config: AppConfig, db: Database, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._db = db
        self._previous_library_widget = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(28, 8, 28, 0)
        bar.addStretch(1)
        self.btn_android_export = QPushButton("Exporter vers Android")
        self.btn_android_export.setProperty("primary", True)
        self.btn_android_export.clicked.connect(self._open_android_export)
        bar.addWidget(self.btn_android_export)
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
        self.media_tabs.currentChanged.connect(self._sync_content_actions)

        self.widgets_page = LibraryPage(config, db)
        self._stack.addWidget(self.widgets_page)

        from audio_video_manager.ui.sections.android_export_dialog import AndroidExportPage

        self.android_export_page = AndroidExportPage(
            self._db.path, Path(self._config.library_root), self
        )
        self.android_export_page.back_requested.connect(self._return_to_library)
        self._stack.addWidget(self.android_export_page)

        self._stack.setCurrentWidget(self.widgets_page)
        self._sync_content_actions(self.media_tabs.currentIndex())

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

    def set_config(self, config: AppConfig) -> None:
        self._config = config
        self.widgets_page.set_config(config)
        self.video_page.set_config(config)
        self.android_export_page.set_library_root(Path(config.library_root))

    def refresh(self) -> None:
        self.widgets_page.refresh()
        self.video_page.refresh()

    def is_busy(self) -> bool:
        android_page = getattr(self, "android_export_page", None)
        return self.video_page.is_busy() or bool(
            android_page and android_page.is_busy()
        )

    def shutdown_background_work(self, *, timeout_ms: int = 12_000) -> bool:
        if not self.video_page.shutdown_background_work(timeout_ms=timeout_ms):
            return False
        if self.android_export_page.is_busy():
            return self.android_export_page.shutdown_background_work(timeout_ms=timeout_ms)
        return True

    def _open_android_export(self) -> None:
        self._previous_library_widget = self._stack.currentWidget()
        self._stack.setCurrentWidget(self.android_export_page)
        self.btn_android_export.hide()
        self.media_tabs.hide()

    def _return_to_library(self) -> None:
        previous = self._previous_library_widget
        if previous is not self.widgets_page:
            previous = self.widgets_page
        self._stack.setCurrentWidget(previous)
        self._previous_library_widget = None
        self.media_tabs.show()
        self._sync_content_actions(self.media_tabs.currentIndex())


    def _sync_content_actions(self, index: int) -> None:
        self.btn_android_export.setVisible(
            index == 0 and self._stack.currentWidget() is self.widgets_page
        )
