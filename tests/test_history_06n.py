"""AVM-06N — sélection cartes Historique, badges, humanisation, actions."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QLabel

from audio_video_manager.storage import Database
from audio_video_manager.ui.progress_labels import humanize_error_for_user
from audio_video_manager.ui.sections.history_page import (
    HistoryPage,
    SelectableJobCard,
    _chip_state_text,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "hist06n.sqlite3")
    database.initialize()
    yield database
    database.close()


@pytest.fixture()
def history_page(qapp, db):
    page = HistoryPage(db)
    yield page
    for i in range(page.list.count()):
        w = page.list.itemWidget(page.list.item(i))
        if isinstance(w, SelectableJobCard):
            w._on_select = lambda _row: None  # noqa: SLF001
    page.list.clear()
    page.close()
    page.deleteLater()
    qapp.processEvents()


def _seed_job(
    db: Database,
    *,
    jid: str,
    state: str,
    error: str | None = None,
    workdir: str | None = None,
    library_path: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, publish_allowed, library_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (jid, state, state, workdir, now, now, now, error, "normal", 1, library_path),
    )
    conn.commit()


def test_chip_state_text_never_includes_recoverable() -> None:
    assert _chip_state_text("Failed") == "Échec"
    assert _chip_state_text("Cancelled") == "Annulé"
    assert "récupér" not in _chip_state_text("Failed").casefold()
    assert len(_chip_state_text("CompletedWithWarnings")) <= 12


def test_humanize_bare_returncode() -> None:
    summary, tech = humanize_error_for_user("freaccmd returncode=4294967293")
    assert "4294967293" not in summary
    assert "extraction" in summary.casefold() or "abouti" in summary.casefold()
    assert tech and "4294967293" in tech


def test_humanize_soft_code_prefix() -> None:
    summary, tech = humanize_error_for_user("code d’extraction = 4294967293")
    assert "4294967293" not in summary
    assert tech and "4294967293" in tech


def test_card_click_selects_and_updates_detail(qapp, db, tmp_path, history_page) -> None:
    wd = tmp_path / "job_tmp"
    wd.mkdir()
    _seed_job(db, jid="j-ok", state="Completed", library_path=str(tmp_path))
    _seed_job(
        db,
        jid="j-fail",
        state="Failed",
        error="freaccmd returncode=4294967293",
        workdir=str(wd),
    )
    page = history_page
    page.resize(1120, 740)
    page.refresh()
    qapp.processEvents()

    assert page.list.count() == 2
    # AVM-10B : bouton dans le layout (pas masqué), désactivé sans éligibilité
    assert not page.btn_resume.isHidden()
    assert not page.btn_resume.isEnabled()

    # Clic simulé : même chemin que mousePressEvent (A-01)
    card0 = page.list.itemWidget(page.list.item(0))
    assert isinstance(card0, SelectableJobCard)
    card0._on_select(card0._row)  # noqa: SLF001
    qapp.processEvents()
    assert page.list.currentRow() == 0
    assert page._selected is not None  # noqa: SLF001
    assert "Sélectionnez" not in page.lbl_detail.text()

    card1 = page.list.itemWidget(page.list.item(1))
    assert isinstance(card1, SelectableJobCard)
    card1._on_select(card1._row)  # noqa: SLF001
    qapp.processEvents()
    assert page.list.currentRow() == 1
    assert page._selected and page._selected.id == "j-fail"  # noqa: SLF001
    assert "Échec" in page.lbl_detail.text()
    # Résumé humanisé dans le panneau
    assert "4294967293" not in page.lbl_detail.text()
    assert "4294967293" in page.txt_detail.toPlainText()  # détail technique


def test_keyboard_row_change_updates_detail(qapp, db, history_page) -> None:
    _seed_job(db, jid="a", state="Completed")
    _seed_job(db, jid="b", state="Abandoned")
    page = history_page
    page.refresh()
    page.select_row(0)
    assert "Terminé" in page.lbl_detail.text()
    page.list.setCurrentRow(1)
    qapp.processEvents()
    assert "Abandonné" in page.lbl_detail.text()


def test_no_horizontal_overflow_at_widths(qapp, db, history_page) -> None:
    _seed_job(
        db,
        jid="wide",
        state="Failed",
        error="freaccmd returncode=4294967293 Workdir=/very/long/path/here",
    )
    page = history_page
    for w, h in ((820, 640), (980, 680), (1120, 740)):
        page.resize(QSize(w, h))
        qapp.processEvents()
        page.refresh()
        qapp.processEvents()
        hbar = page.list.horizontalScrollBar()
        assert page.list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert hbar.maximum() == 0 or hbar.value() == 0
        vp_w = max(160, page.list.viewport().width())
        for i in range(page.list.count()):
            item = page.list.item(i)
            card = page.list.itemWidget(item)
            assert card is not None
            assert card.maximumWidth() <= vp_w + 8


def test_badges_short_and_recoverable_separate(qapp, db, tmp_path, history_page) -> None:
    wd = tmp_path / "tmp"
    wd.mkdir()
    _seed_job(db, jid="f", state="Failed", error="x", workdir=str(wd))
    page = history_page
    page.refresh()
    card = page.list.itemWidget(page.list.item(0))
    chips = [
        c
        for c in card.findChildren(QLabel)
        if c.objectName() in {"chip", "chipWarn", "chipErr"}
    ]
    texts = [c.text() for c in chips]
    assert "Échec" in texts
    assert any(t == "Récupérable" for t in texts)
    assert all("·" not in t for t in texts)


def test_table_api_still_works(qapp, db, history_page) -> None:
    """Compat 06H : selectRow sur table masquée."""
    _seed_job(db, jid="t", state="Completed")
    page = history_page
    page.refresh()
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    qapp.processEvents()
    assert "Terminé" in page.lbl_detail.text()
