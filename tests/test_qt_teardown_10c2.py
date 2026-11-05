"""AVM-10C.2 — non-régression teardown central (sans os._exit, sans GC forcé)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.theme import apply_app_style
from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage
from tests.qt_support import dispose_widget, drain_deferred_deletes, shutdown_all_widgets


@pytest.fixture()
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_app_style(app)
    return app


def test_dispose_orphan_wizard_clears_toplevel(qapp, tmp_path) -> None:
    db = Database(tmp_path / "a.sqlite3")
    db.initialize()
    cfg = AppConfig(
        library_root=str(tmp_path / "lib"),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
    )
    page = ArchiveWizardPage(cfg, db)
    page.show()
    qapp.processEvents()
    assert page in qapp.topLevelWidgets() or page.isVisible()
    dispose_widget(page)
    drain_deferred_deletes()
    # Plus de wizard vivant parmi les top-level
    names = [type(w).__name__ for w in qapp.topLevelWidgets()]
    assert "ArchiveWizardPage" not in names
    db.close()


def test_shutdown_all_after_mainwindow(qapp, tmp_path) -> None:
    db = Database(tmp_path / "b.sqlite3")
    db.initialize()
    cfg = AppConfig(
        library_root=str(tmp_path / "lib"),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
        library_ui_mode="qml",
    )
    win = MainWindow(cfg, db)
    win.show()
    qapp.processEvents()
    win.navigate_to(1)
    qapp.processEvents()
    shutdown_all_widgets()
    assert not any(type(w).__name__ == "MainWindow" for w in qapp.topLevelWidgets())
    db.close()
