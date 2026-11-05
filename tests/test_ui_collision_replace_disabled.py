"""AVM-06C — Replace désactivé sans confirmation explicite."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.storage import Database
from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_replace_disabled_defaults_to_rename(qapp, tmp_path) -> None:
    cfg = AppConfig(library_root=str(tmp_path / "lib"), jobs_dir=str(tmp_path / "jobs"))
    db = Database(tmp_path / "t.sqlite3")
    db.initialize()
    page = ArchiveWizardPage(cfg, db)
    assert page.radio_rename.isChecked()
    assert not page.radio_replace.isEnabled()
    assert page._collision_policy() == CollisionPolicy.RENAME  # noqa: SLF001
    # même si on force le radio (ne devrait pas arriver via UI)
    page.radio_replace.setChecked(True)
    assert page._collision_policy() == CollisionPolicy.RENAME  # noqa: SLF001
    db.close()
