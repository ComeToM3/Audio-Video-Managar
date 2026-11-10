"""AVM-10C.1 — non-régression teardown Widgets et threads."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.theme import apply_app_style


@pytest.fixture()
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_app_style(app)
    return app


def test_no_running_qthread_after_close(qapp, tmp_path) -> None:
    from PySide6.QtCore import QThread
    from shiboken6 import isValid

    db = Database(tmp_path / "t2.sqlite3")
    db.initialize()
    cfg = AppConfig(
        library_root=str(tmp_path / "lib"),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
    )
    win = MainWindow(cfg, db)
    win.show()
    qapp.processEvents()
    win.close()
    win.deleteLater()
    qapp.processEvents()
    running = []
    import gc

    for obj in gc.get_objects():
        if isinstance(obj, QThread) and isValid(obj):
            try:
                if obj.isRunning():
                    running.append(type(obj).__name__)
            except RuntimeError:
                pass
    assert running == []
    db.close()
