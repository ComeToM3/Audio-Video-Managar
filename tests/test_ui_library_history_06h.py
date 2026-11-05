"""AVM-06H — Bibliothèque, Historique, progression, shell."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.storage.catalog import (
    list_jobs,
    list_releases,
    list_tracks_for_release,
    mark_job_abandoned,
    state_label_fr,
)
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.progress_labels import PIPELINE_STEPS, progress_step_index
from audio_video_manager.ui.sections.history_page import HistoryPage
from audio_video_manager.ui.sections.library_page import LibraryPage
from audio_video_manager.ui.wizard.archive_wizard import STEP_LABELS


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
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
        library_ui_mode="widgets",
    )


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "ui06h.sqlite3")
    database.initialize()
    yield database
    database.close()


def _seed_release(db: Database, album_dir: Path) -> int:
    album_dir.mkdir(parents=True, exist_ok=True)
    (album_dir / "01 - Track.flac").write_bytes(b"f")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    cur = conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("disc", "mbid", "Queen", "Greatest Hits", 1992, str(album_dir), "imported", now),
    )
    rid = int(cur.lastrowid)
    conn.execute(
        """
        INSERT INTO tracks(release_id, number, title, path, duration_ms, flac_ok, rip_check_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (rid, 1, "We Will Rock You", str(album_dir / "01 - Track.flac"), 122000, 1, "ok"),
    )
    conn.commit()
    return rid


def _seed_job(db: Database, *, state: str = "Failed", library_path: str | None = None) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    jid = "job06h" + state[:4]
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, publish_allowed, warnings_json, library_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            jid,
            state,
            state,
            None,
            now,
            now,
            now,
            "exemple",
            "normal",
            1,
            '["avertissement test"]',
            library_path,
        ),
    )
    conn.commit()
    return jid


def test_step_labels_five_french() -> None:
    assert len(STEP_LABELS) == 5
    assert "Disque" in STEP_LABELS[0]
    assert "Identification" in STEP_LABELS[1]
    assert "Approbation" in STEP_LABELS[2]
    assert "Extraction" in STEP_LABELS[3]
    assert "publication" in STEP_LABELS[3].casefold()
    assert "Terminé" in STEP_LABELS[4]


def test_progress_step_index() -> None:
    assert progress_step_index("Contrôle d’intégrité") == PIPELINE_STEPS.index(
        "Contrôle des fichiers"
    )
    assert progress_step_index("Publication bibliothèque C") == PIPELINE_STEPS.index(
        "Publication"
    )


def test_catalog_releases_and_tracks(db, tmp_path) -> None:
    album = tmp_path / "Queen" / "Hits"
    rid = _seed_release(db, album)
    releases = list_releases(db)
    assert len(releases) == 1
    assert releases[0].album_artist == "Queen"
    assert releases[0].path_exists is True
    tracks = list_tracks_for_release(db, rid)
    assert len(tracks) == 1
    assert tracks[0].title.startswith("We Will")


def test_catalog_jobs_and_abandon(db) -> None:
    jid = _seed_job(db, state="Failed")
    jobs = list_jobs(db)
    assert any(j.id == jid for j in jobs)
    assert state_label_fr("Failed") == "Échec"
    mark_job_abandoned(db, jid)
    again = list_jobs(db)
    abandoned = next(j for j in again if j.id == jid)
    assert abandoned.state == "Abandoned"
    assert "non supprimés" in (abandoned.error_summary or "")


def test_library_page_lists_album(qapp, config, db, tmp_path) -> None:
    album = Path(config.library_root) / "Queen" / "Hits"
    _seed_release(db, album)
    page = LibraryPage(config, db)
    page.refresh()
    assert page.list.count() == 1
    assert "Queen" in page.list.item(0).text()
    page.list.setCurrentRow(0)
    assert page.tbl_tracks.rowCount() == 1
    assert page.btn_open_album.isEnabled()


def test_library_search_filter(qapp, config, db, tmp_path) -> None:
    _seed_release(db, Path(config.library_root) / "A" / "B")
    page = LibraryPage(config, db)
    page.refresh()
    page.search.setText("zzzz-absent")
    assert page.list.count() == 0
    page.search.setText("Queen")
    assert page.list.count() == 1


def test_history_page_lists_and_detail(qapp, config, db) -> None:
    _seed_job(db, state="Completed")
    page = HistoryPage(db)
    page.refresh()
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    assert "Terminé" in page.lbl_detail.text() or "avertissement" in page.txt_detail.toPlainText()


def test_main_window_uses_real_library_history(qapp, config, db, tmp_path) -> None:
    from audio_video_manager.ui.sections.library_host import LibraryHost

    _seed_release(db, Path(config.library_root) / "X" / "Y")
    _seed_job(db, state="Failed")
    win = MainWindow(config, db)
    assert isinstance(win.page_library, (LibraryPage, LibraryHost))
    assert isinstance(win.page_history, HistoryPage)
    win.navigate_to(1)
    assert win.current_section() == 1
    assert win.page_library.list.count() >= 1
    win.navigate_to(2)
    assert win.page_history.table.rowCount() >= 1
    # A3 : retour archive OK
    win.navigate_to(0)
    assert win.wizard.current_step() == 0


def test_wizard_has_progress_steps_and_history_button(qapp, config, db) -> None:
    win = MainWindow(config, db)
    wiz = win.wizard
    assert wiz.list_progress_steps.count() == len(PIPELINE_STEPS) - 1
    assert wiz.btn_goto_history is not None
    # signal navigation historique
    seen: list[int] = []
    wiz.request_navigate.connect(seen.append)
    wiz.btn_goto_history.click()
    assert seen == [2]
