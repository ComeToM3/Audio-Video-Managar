"""AVM-06L — design system, grille bibliothèque, historique cartes, garde-fous UX."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QListWidget, QStyleFactory

from audio_video_manager.config import AppConfig
from audio_video_manager.library.duplicates import DuplicateGate, assess_from_sheet
from audio_video_manager.metadata.enums import CoverStatus, FieldTrust
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.models import FieldMeta
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow, NARROW_BREAKPOINT
from audio_video_manager.ui.sections.history_page import HistoryPage
from audio_video_manager.ui.sections.library_page import LibraryPage
from audio_video_manager.ui.theme import TOKEN, apply_app_style
from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    apply_app_style(app)
    return app


@pytest.fixture()
def config(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    return AppConfig(
        library_root=str(lib),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "ui06l.sqlite3")
    database.initialize()
    yield database
    database.close()


def _seed_release(db: Database, album_dir: Path) -> int:
    album_dir.mkdir(parents=True, exist_ok=True)
    (album_dir / "cover.jpg").write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xd9"
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    cur = conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("demo.disc.id", "mbid-a", "Queen", "Greatest Hits", 1992, str(album_dir), "imported", now),
    )
    rid = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO tracks(release_id, number, title, path, duration_ms, flac_ok, rip_check_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (rid, 1, "Killer Queen", str(album_dir / "01.flac"), 180000, 1, "ok"),
    )
    conn.commit()
    return rid


def _seed_job(db: Database, *, state: str = "Completed") -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    jid = "job06l" + state[:4]
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, publish_allowed, library_path, disc_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (jid, state, state, None, now, now, now, None, "normal", 1, None, "demo.disc.id"),
    )
    conn.commit()
    return jid


def test_theme_tokens_and_fusion(qapp) -> None:
    # AVM-08D.1 — palette officielle
    assert TOKEN["accent"] == "#F1B65C"
    assert TOKEN["bg"] == "#17191F"
    assert TOKEN["iris"] == "#7D8FE8"
    sheet = qapp.styleSheet()
    assert "#F1B65C" in sheet
    assert "#17191F" in sheet
    assert "fusion" in {s.casefold() for s in QStyleFactory.keys()}


def test_library_icon_grid(qapp, config, db, tmp_path) -> None:
    _seed_release(db, Path(config.library_root) / "Queen" / "Hits")
    page = LibraryPage(config, db)
    page.refresh()
    assert page.list.count() == 1
    assert page.list.viewMode() == QListWidget.ViewMode.IconMode
    assert page.list.objectName() == "albumGrid"
    assert "Queen" in page.list.item(0).text()
    page.list.setCurrentRow(0)
    assert page.btn_open_album.isEnabled()
    assert page.tbl_tracks.rowCount() == 1


def test_library_empty_state(qapp, config, db) -> None:
    page = LibraryPage(config, db)
    page.refresh()
    assert page.list.count() == 0
    # Hors fenêtre : isVisible() est faux ; isHidden() reflète setVisible
    assert not page.empty_card.isHidden()
    assert page.list.isHidden()


def test_library_missing_folder_chip(qapp, config, db, tmp_path) -> None:
    gone = tmp_path / "gone" / "album"
    # insert without creating dir
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("x", "y", "Ghost", "Missing", 2000, str(gone), "imported", now),
    )
    conn.commit()
    page = LibraryPage(config, db)
    page.refresh()
    assert page.list.count() == 1
    page.list.setCurrentRow(0)
    assert "manqu" in page.chip_status.text().casefold()


def test_history_cards_and_table_api(qapp, config, db) -> None:
    _seed_job(db, state="Failed")
    page = HistoryPage(db)
    page.refresh()
    assert page.table.rowCount() == 1
    assert page.list.count() == 1
    page.table.selectRow(0)
    assert page.lbl_detail.text()
    assert "Échec" in page.lbl_detail.text() or "échec" in page.txt_detail.toPlainText().casefold()


def test_wizard_w4_has_cover_and_dup_banner(qapp, config, db) -> None:
    page = ArchiveWizardPage(config, db)
    assert page.lbl_w4_cover is not None
    assert page.lbl_w4_dup is not None
    assert page.list_progress_steps.count() >= 1
    # Stepper pastilles
    assert all(b.property("step") for b in page._step_buttons)  # noqa: SLF001


def test_duplicate_ux_prefers_open_path(qapp, config, db, tmp_path) -> None:
    album = Path(config.library_root) / "Queen" / "Hits"
    _seed_release(db, album)
    (album / "01.flac").write_bytes(b"complete fixture track")
    sheet = make_approvable_sheet(
        album="Greatest Hits", artist="Queen", year=1992, tracks=1
    )
    sheet.edition.musicbrainz_release_id = "mbid-a"
    sheet.edition.cover_status = CoverStatus.CONFIRMED
    sheet.edition.cover_path_or_url = "https://example.test/c.jpg"
    sheet.edition.field_meta["cover_status"] = FieldMeta(trust=FieldTrust.CONFIRMED)
    approve_sheet(sheet, note="t")
    assessment = assess_from_sheet(db, sheet)
    assert assessment.gate == DuplicateGate.REQUIRE_CONFIRM
    page = ArchiveWizardPage(config, db)
    path = page._existing_album_path(assessment)  # noqa: SLF001
    assert path is not None
    assert path.is_dir()


def test_narrow_breakpoint_still_works(qapp, config, db) -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QResizeEvent

    win = MainWindow(config, db)
    win.show()
    qapp.processEvents()
    old = QSize(1100, 720)
    new = QSize(NARROW_BREAKPOINT - 40, 600)
    win.resize(new)
    win.resizeEvent(QResizeEvent(new, old))
    qapp.processEvents()
    # AVM-08D.1 : rail gauche compact ; shims masqués
    assert not win.nav.isVisible()
    assert not win.tab_bar.isVisible()
    assert len(win._side_buttons) == 4  # noqa: SLF001
    assert win._side_buttons[0].text() == "Arch."  # noqa: SLF001
