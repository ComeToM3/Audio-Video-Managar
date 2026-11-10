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


def test_collision_policy_defaults_to_rename_without_replace_controls(qapp, tmp_path) -> None:
    cfg = AppConfig(library_root=str(tmp_path / "lib"), jobs_dir=str(tmp_path / "jobs"))
    db = Database(tmp_path / "t.sqlite3")
    db.initialize()
    page = ArchiveWizardPage(cfg, db)
    assert not hasattr(page, "radio_rename")
    assert not hasattr(page, "radio_replace")
    assert page._collision_policy() == CollisionPolicy.RENAME  # noqa: SLF001
    db.close()
