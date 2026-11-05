"""AVM-06 — UI-0 shell + UI-1 structure (sans rip réel)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.metadata.enums import ApprovalState, CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.approval_fingerprint import compute_approval_fingerprint
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import NAV_ARCHIVE, MainWindow, NARROW_BREAKPOINT
from audio_video_manager.ui.wizard.archive_wizard import STEP_LABELS, ArchiveWizardPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def config(tmp_path):
    return AppConfig(
        library_root=str(tmp_path / "lib"),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
        library_ui_mode="widgets",  # évite QML dans tests shell (repli 08B)
    )


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.sqlite3")
    database.initialize()
    yield database
    database.close()


def test_main_window_four_sections(qapp, config, db) -> None:
    win = MainWindow(config, db)
    assert win.nav.count() == 4
    assert win.tab_bar.count() == 4
    assert win.stack.count() == 4
    assert win.current_section() == NAV_ARCHIVE
    assert "Archiver" in win.nav.item(0).text()
    # Pas de probes au lancement
    assert win.wizard.current_step() == 0


def test_navigate_preserves_wizard_approval(qapp, config, db) -> None:
    win = MainWindow(config, db)
    sheet = make_approvable_sheet()
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="ui")
    win.wizard._sheet = sheet  # noqa: SLF001 — injection test session
    win.wizard._approved_fp = compute_approval_fingerprint(sheet)  # noqa: SLF001
    assert win.wizard.sheet().approval == ApprovalState.APPROVED

    win.navigate_to(1)  # Bibliothèque
    assert win.current_section() == 1
    win.navigate_to(0)  # retour Archiver
    assert win.wizard.sheet().approval == ApprovalState.APPROVED
    assert win.wizard.approval_fingerprint() is not None


def test_wizard_five_steps_and_no_dvd(qapp, config, db) -> None:
    page = ArchiveWizardPage(config, db)
    assert len(STEP_LABELS) == 5
    assert page.current_step() == 0
    text = page.lbl_disc.text().casefold()
    assert "dvd" not in text
    # stepper labels
    joined = " ".join(STEP_LABELS).casefold()
    assert "dvd" not in joined


def test_settings_tech_test_in_advanced_only(qapp, config, db) -> None:
    from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

    win = MainWindow(config, db)
    settings = win.page_settings
    boxes = settings.findChildren(QCheckBox)
    auto = [b for b in boxes if "auto-approuver" in b.text().casefold()]
    assert auto and not auto[0].isEnabled() and not auto[0].isChecked()
    tech = [
        b
        for b in settings.findChildren(QPushButton)
        if "test technique" in b.text().casefold()
    ]
    assert len(tech) == 1
    dvd_labels = [l for l in settings.findChildren(QLabel) if "dvd" in l.text().casefold()]
    assert dvd_labels
    assert "non disponible" in dvd_labels[0].text().casefold()


def test_narrow_shows_tabs(qapp, config, db) -> None:
    """AVM-08D.1 : rail compact en étroit ; shims nav/tab toujours masqués."""
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QResizeEvent

    from audio_video_manager.ui.main_window import SIDE_NARROW, SIDE_WIDE

    win = MainWindow(config, db)
    win.show()
    qapp.processEvents()
    old = QSize(1100, 720)
    new = QSize(NARROW_BREAKPOINT - 40, 600)
    win.resize(new)
    win.resizeEvent(QResizeEvent(new, old))
    qapp.processEvents()
    assert not win.nav.isVisible()
    assert not win.tab_bar.isVisible()
    assert win._side.width() == SIDE_NARROW  # noqa: SLF001
    assert win._side_buttons[1].text() == "Bibl."  # noqa: SLF001

    wide = QSize(1100, 720)
    win.resize(wide)
    win.resizeEvent(QResizeEvent(wide, new))
    qapp.processEvents()
    assert not win.nav.isVisible()
    assert not win.tab_bar.isVisible()
    assert win._side.width() == SIDE_WIDE  # noqa: SLF001
    assert win._side_buttons[1].text() == "Bibliothèque"  # noqa: SLF001


def test_wizard_edit_after_approve_revokes(qapp, config, db) -> None:
    page = ArchiveWizardPage(config, db)
    sheet = make_approvable_sheet()
    sheet.edition.cover_status = CoverStatus.UNAVAILABLE
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.UNAVAILABLE)
    approve_sheet(sheet, note="ui")
    page._sheet = sheet  # noqa: SLF001
    page._approved_fp = compute_approval_fingerprint(sheet)  # noqa: SLF001
    page._set_step(2)  # noqa: SLF001
    page.edit_album.setText("Titre changé après approbation")
    qapp.processEvents()
    assert page.sheet().approval == ApprovalState.PENDING
    assert page.approval_fingerprint() is None
