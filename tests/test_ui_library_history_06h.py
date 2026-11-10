"""AVM-06H — Bibliothèque, Historique, progression, shell."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.storage.catalog import (
    list_jobs,
    list_releases,
    list_tracks_for_release,
    mark_job_abandoned,
    state_label_fr,
)
from audio_video_manager.library.android_export import AndroidCandidate, AndroidDevice
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.progress_labels import PIPELINE_STEPS, progress_step_index
from audio_video_manager.ui.sections.history_page import HistoryPage
from audio_video_manager.ui.sections.android_export_dialog import AndroidExportPage
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


def test_step_labels_four_cd_french() -> None:
    assert len(STEP_LABELS) == 4
    assert "Disque" in STEP_LABELS[0]
    assert "Fiche" in STEP_LABELS[1]
    assert "Extraction" in STEP_LABELS[2]
    assert "Terminé" in STEP_LABELS[3]


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
    assert tracks[0].id is not None
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


def test_library_manual_cover_add_replace_and_persist(
    qapp, config, db, tmp_path, monkeypatch
) -> None:
    album = Path(config.library_root) / "Queen" / "Hits"
    _seed_release(db, album)
    first_image = tmp_path / "manual-first.png"
    second_image = tmp_path / "manual-second.png"
    for path, color in ((first_image, 0xFF336699), (second_image, 0xFFCC5533)):
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(color)
        assert image.save(str(path), "PNG")

    selected_paths = iter((str(first_image), str(second_image), str(second_image)))
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (next(selected_paths), "PNG"),
    )
    answers = iter((QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: next(answers))

    page = LibraryPage(config, db)
    page.refresh()
    page.list.setCurrentRow(0)
    assert page.btn_cover.isEnabled()

    page.btn_cover.click()
    destination = album / "cover.jpg"
    first_bytes = first_image.read_bytes()
    assert destination.read_bytes() == first_bytes
    assert not page.cover_label.pixmap().isNull()

    page.btn_cover.click()
    assert destination.read_bytes() == first_bytes

    page.btn_cover.click()
    second_bytes = second_image.read_bytes()
    assert destination.read_bytes() == second_bytes
    assert not page.cover_label.pixmap().isNull()

    reopened = LibraryPage(config, db)
    reopened.refresh()
    reopened.list.setCurrentRow(0)
    assert destination.is_file()
    assert not reopened.cover_label.pixmap().isNull()


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
    assert win.page_library._stack.count() == 2
    assert not hasattr(win.page_library, "using_qml")
    assert win.page_library.btn_android_export.text() == "Exporter vers Android"
    assert win.wizard._collision_policy().value == "rename"
    assert not hasattr(win.wizard, "chk_publish")
    assert not hasattr(win.wizard, "radio_skip")
    assert not hasattr(win.wizard, "radio_replace")
    host = win.page_library
    assert host.media_tabs.count() == 2
    host.media_tabs.setCurrentIndex(1)
    assert host._media_stack.currentWidget() is host.video_page
    assert host.btn_android_export.isHidden()
    host.media_tabs.setCurrentIndex(0)
    assert host._media_stack.currentWidget() is host._stack
    assert not host.btn_android_export.isHidden()
    assert isinstance(win.page_history, HistoryPage)
    win.navigate_to(1)
    assert win.current_section() == 1
    assert win.page_library.list.count() >= 1
    win.navigate_to(2)
    assert win.page_history.table.rowCount() >= 1
    # A3 : retour archive OK
    win.navigate_to(0)
    assert win.wizard.current_step() == 0


def test_android_export_page_selects_tracks_and_returns_to_library(qapp, config, db) -> None:
    from audio_video_manager.ui.sections.library_host import LibraryHost

    host = LibraryHost(config, db)
    page = host.android_export_page
    assert not page.isWindow()
    candidates = [
        AndroidCandidate(
            track_id=1, release_id=10, artist="Queen", album="Album", year=2024,
            number=1, title="Song", source_path="missing.flac", source_size_bytes=100,
            source_mtime_ns=1, relative_path="Queen/Album/01 - Song.flac",
            destination_path="/sdcard/Music/AudioVideoManager/Queen/Album/01 - Song.flac",
            source_sha256=None, status="new",
        ),
        AndroidCandidate(
            track_id=2, release_id=10, artist="Queen", album="Album", year=2024,
            number=2, title="Unavailable", source_path="missing-2.flac", source_size_bytes=0,
            source_mtime_ns=0, relative_path="", destination_path="",
            source_sha256=None, status="source_missing",
        ),
    ]
    page._populate_tree(candidates)
    album = page.tree.topLevelItem(0)
    assert album.childCount() == 2
    album.setCheckState(0, Qt.CheckState.Checked)
    assert page._selected_candidates() == [candidates[0]]
    assert "1 fichier sélectionné" in page.lbl_selection.text()
    page.device_combo.addItem("Second device", AndroidDevice("SECOND", "device", ""))
    page.device_combo.setCurrentIndex(1)
    assert page.tree.topLevelItemCount() == 0
    assert page._selected_candidates() == []

    host.btn_android_export.click()
    assert host._stack.currentWidget() is page
    assert page.isWindow() is False
    assert host.media_tabs.isHidden()
    page.btn_back.click()
    assert host._stack.currentWidget() is host.widgets_page
    assert not host.media_tabs.isHidden()


def test_archive_progress_uses_track_events_and_keeps_navigation_available(
    qapp, config, db
) -> None:
    from audio_video_manager.metadata.factories import make_approvable_sheet

    win = MainWindow(config, db)
    wizard = win.wizard
    wizard._sheet = make_approvable_sheet(tracks=3)
    wizard._archive_active = True
    wizard._busy = True
    win._on_busy(True)

    wizard._on_archive_progress(
        "Processing file: Audio CD 0 - Track 2...done.", None
    )

    assert wizard.lbl_progress.text().startswith("Piste 2/3 terminée")
    assert wizard.lbl_track_progress.text() == "1 piste terminée sur 3"
    assert wizard.progress.minimum() == 0
    assert wizard.progress.maximum() == 0
    assert win.archive_status_label.text() == wizard.lbl_progress.text()
    assert win.archive_status_progress.maximum() == 0
    assert all(button.isEnabled() for button in win._side_buttons.values())

    win.navigate_to(1)
    assert win.current_section() == 1
    assert wizard.lbl_progress.text().startswith("Piste 2/3 terminée")

    wizard._on_archive_progress("Progress 42%", 0.42)
    assert wizard.progress.maximum() == 100
    assert wizard.progress.value() == 42
    assert win.archive_status_progress.maximum() == 100
    assert win.archive_status_progress.value() == 42
    assert "fre:ac" in wizard.progress.format()
    wizard._highlight_progress_step(
        wizard.list_progress_steps.count() - 1,
        completed=True,
        warning=True,
    )
    assert wizard.list_progress_steps.item(
        wizard.list_progress_steps.count() - 1
    ).text().startswith("Terminée avec avertissements")


def test_ambiguous_preselection_cannot_be_approved(qapp, config, db, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox
    from audio_video_manager.metadata.factories import make_approvable_sheet

    window = MainWindow(config, db)
    wizard = window.wizard
    wizard._sheet = make_approvable_sheet(tracks=2)
    wizard._manual_edition_choice_required = True
    messages = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *_args: messages.append(_args[2])
    )

    assert wizard._do_approve() is False
    assert wizard._sheet.approval.value == "Pending"
    assert messages and "choisissez explicitement" in messages[0].casefold()


def test_user_activation_confirms_the_preselected_edition(qapp, config, db, monkeypatch) -> None:
    from audio_video_manager.metadata.factories import make_approvable_sheet
    from audio_video_manager.metadata.enums import FieldTrust
    from audio_video_manager.metadata.musicbrainz_client import ReleaseCandidate

    window = MainWindow(config, db)
    wizard = window.wizard
    wizard._sheet = make_approvable_sheet(tracks=2)
    candidate = ReleaseCandidate(
        release_id="manual-release",
        title="Chosen Album",
        artist_credit="Chosen Artist",
        year=2000,
        country="CA",
        track_titles=["Track One", "Track Two"],
        track_artists=["Chosen Artist", "Chosen Artist"],
        track_durations_ms=[180_000, 181_000],
        matched_medium_position=1,
        medium_count=1,
        toc_match="exact",
    )
    wizard._candidates = [candidate]
    wizard._candidate_loading = True
    wizard.combo_editions.clear()
    wizard.combo_editions.addItem("Chosen Artist — Chosen Album", candidate.release_id)
    wizard.combo_editions.setCurrentIndex(0)
    wizard._candidate_loading = False
    wizard._selected_candidate_id = candidate.release_id
    wizard._manual_edition_choice_required = True
    monkeypatch.setattr(wizard, "_start_edition_enrichment", lambda *_args: None)

    wizard.combo_editions.activated.emit(0)

    assert wizard._manual_edition_choice_required is False
    assert wizard._sheet.edition.field_meta["album_title"].trust == FieldTrust.CONFIRMED
    assert "confirmée par votre sélection" in wizard.lbl_id_status.text().casefold()


def test_reset_session_clears_previous_archive_tracking(qapp, config, db) -> None:
    window = MainWindow(config, db)
    wizard = window.wizard
    wizard._completed_track_numbers.update({1, 2})
    wizard._highlight_progress_step(wizard.list_progress_steps.count() - 1, completed=True)
    wizard.lbl_progress.setText("Archivage terminé; album publié et vérifié.")
    wizard.lbl_track_progress.setText("2 pistes terminées sur 2")
    wizard.progress.setRange(0, 100)
    wizard.progress.setValue(100)
    wizard.progress.setTextVisible(True)
    wizard.archive_status_changed.emit(
        "Archivage terminé; album publié et vérifié.", 1.0, False
    )

    wizard._reset_session()

    assert wizard._completed_track_numbers == set()
    assert all(
        wizard.list_progress_steps.item(index).text().startswith("À venir —")
        for index in range(wizard.list_progress_steps.count())
    )
    assert wizard.lbl_track_progress.text() == "Aucune piste terminée."
    assert wizard.lbl_progress.text() == "En attente du lancement…"
    assert wizard.progress.maximum() == 1
    assert window.archive_status_label.text() == ""
    assert window.archive_status_label.isHidden()
    assert window.archive_status_progress.isHidden()


def test_new_disc_resets_tracking_and_leaves_result_page(qapp, config, db) -> None:
    from audio_video_manager.metadata.factories import make_approvable_sheet
    from audio_video_manager.metadata.toc_reader import DiscReadResult

    window = MainWindow(config, db)
    wizard = window.wizard
    sheet = make_approvable_sheet(tracks=2)
    wizard._sheet = sheet
    wizard._disc_read = DiscReadResult(
        sheet.identity.disc_id, sheet.identity.toc, "D:"
    )
    wizard._active_job_id = "previous-job"
    wizard._highlight_progress_step(wizard.list_progress_steps.count() - 1, completed=True)
    wizard._set_step(wizard.PAGE_DONE)
    wizard.archive_status_changed.emit("Ancien archivage terminé.", 1.0, False)

    changed = wizard._accept_disc_read(
        DiscReadResult("new-disc-id", sheet.identity.toc, "D:")
    )

    assert changed is True
    assert wizard.current_step() == wizard.PAGE_DISC
    assert wizard._sheet is None
    assert wizard._active_job_id is None
    assert all(
        wizard.list_progress_steps.item(index).text().startswith("À venir —")
        for index in range(wizard.list_progress_steps.count())
    )
    assert window.archive_status_label.isHidden()


def test_late_archive_events_cannot_change_active_job(qapp, config, db) -> None:
    from types import SimpleNamespace
    from audio_video_manager.metadata.factories import make_approvable_sheet

    window = MainWindow(config, db)
    wizard = window.wizard
    wizard._sheet = make_approvable_sheet(tracks=2)
    wizard._active_job_id = "current-job"
    wizard._archive_active = True

    wizard._on_archive_progress(
        "Processing file: Audio CD 0 - Track 1...done.", None, "previous-job"
    )
    wizard._on_archive_finished(SimpleNamespace(job_id="previous-job"))
    wizard._on_archive_failed("late failure", "previous-job")

    assert wizard._completed_track_numbers == set()
    assert wizard._archive_active is True
    assert wizard.lbl_done.text() == "—"

    wizard._on_archive_progress(
        "Processing file: Audio CD 0 - Track 1...done.", None, "current-job"
    )
    assert wizard._completed_track_numbers == {1}
    assert wizard.lbl_track_progress.text() == "1 piste terminée sur 2"

    current_worker = SimpleNamespace(job_id="current-job")
    current_thread = object()
    wizard._worker = current_worker
    wizard._thread = current_thread
    wizard._clear_thread("previous-job")
    assert wizard._worker is current_worker
    assert wizard._thread is current_thread


def test_new_archive_starts_with_its_own_active_step(qapp, config, db, monkeypatch) -> None:
    from types import SimpleNamespace
    from audio_video_manager.extraction.drives import CdDrive
    from audio_video_manager.metadata.factories import make_approvable_sheet
    from audio_video_manager.metadata.toc_reader import DiscReadResult
    from audio_video_manager.metadata.validation import approve_sheet
    import audio_video_manager.ui.wizard.archive_wizard as archive_wizard_module

    class FakeThread:
        def start(self) -> None:
            pass

    class FakeWorker:
        def __init__(self, **_kwargs) -> None:
            self.job_id = "new-job"

    window = MainWindow(config, db)
    wizard = window.wizard
    sheet = make_approvable_sheet(tracks=2)
    approve_sheet(sheet, note="simulated second archive")
    wizard._sheet = sheet
    wizard._disc_read = DiscReadResult(sheet.identity.disc_id, sheet.identity.toc, "D:")
    wizard._populate_freac_drives([CdDrive(0, "1:0:0", "Test CD drive")])
    wizard._prompt_rearchive_if_needed = lambda: True
    monkeypatch.setattr(
        archive_wizard_module,
        "probe_freaccmd",
        lambda **_kwargs: SimpleNamespace(found=True, path=Path("freaccmd.exe")),
    )
    monkeypatch.setattr(archive_wizard_module, "ArchiveWorker", FakeWorker)
    callbacks = {}

    def attach(_worker, **kwargs):
        callbacks.update(kwargs)
        return FakeThread()

    monkeypatch.setattr(archive_wizard_module, "attach_worker_thread", attach)

    wizard._start_archive()

    assert wizard._active_job_id == "new-job"
    assert wizard._archive_active is True
    assert wizard._completed_track_numbers == set()
    assert wizard.lbl_progress.text() == "Vérification du disque…"
    assert wizard.list_progress_steps.item(0).text().startswith("En cours —")
    assert all(
        wizard.list_progress_steps.item(index).text().startswith("À venir —")
        for index in range(1, wizard.list_progress_steps.count())
    )
    callbacks["progress_slot"]("Extraction fre:ac → zone A…", None, "new-job")
    assert wizard.list_progress_steps.item(0).text().startswith("Réussie —")
    assert wizard.list_progress_steps.item(1).text().startswith("En cours —")
    assert all(
        wizard.list_progress_steps.item(index).text().startswith("À venir —")
        for index in range(2, wizard.list_progress_steps.count())
    )


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
