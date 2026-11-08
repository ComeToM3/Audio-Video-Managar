"""AVM-06O — finitions UX/UI (chemins, Disc ID, scroll Paramètres, statut header)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QScrollArea, QStyleFactory

from audio_video_manager.config import AppConfig, load_config
from audio_video_manager.extraction.cd_ripper import RipResult
from audio_video_manager.library.publish import CollisionPolicy, PublishResult
from audio_video_manager.metadata.enums import JobMode
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.orchestration.archive_job import ArchiveJobReport
from audio_video_manager.orchestration.rip_job import RipJobReport
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow, NAV_ARCHIVE
from audio_video_manager.ui.path_labels import friendly_path_label, path_tooltip
from audio_video_manager.ui.sections.history_page import HistoryPage
from audio_video_manager.ui.sections.library_page import LibraryPage
from audio_video_manager.ui.sections.settings_page import SettingsPage
from audio_video_manager.ui.theme import apply_app_style
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
    database = Database(tmp_path / "ui06o.sqlite3")
    database.initialize()
    yield database
    database.close()


def test_friendly_path_label_last_segments() -> None:
    assert friendly_path_label("") == "—"
    assert friendly_path_label(None, empty="vide") == "vide"
    p = Path("C:/Users/Demo/Music/Queen/1992 - Greatest Hits")
    label = friendly_path_label(str(p))
    assert "Queen" in label or "Greatest Hits" in label
    assert "Users" not in label
    assert path_tooltip(str(p)) == str(p)


def test_theme_applies_fusion_when_available(qapp) -> None:
    # Fusion est dans les clés ; après setStyleSheet Qt enveloppe en QStyleSheetStyle
    assert "Fusion" in QStyleFactory.keys()
    apply_app_style(qapp)
    assert qapp.styleSheet()
    assert "#F1B65C" in qapp.styleSheet()


def test_w1_disc_id_hidden_by_default(qapp, config, db) -> None:
    from PySide6.QtWidgets import QPushButton

    page = ArchiveWizardPage(config, db)
    page.show()
    qapp.processEvents()
    assert page.btn_tech_details.isCheckable()
    assert not page.btn_tech_details.isChecked()
    assert not page.lbl_disc_details.isVisible()
    page.lbl_disc_details.setText("Disc ID : abc.def")
    page.btn_tech_details.setChecked(True)
    qapp.processEvents()
    assert page.lbl_disc_details.isVisible()
    page.btn_tech_details.setChecked(False)
    qapp.processEvents()
    assert not page.lbl_disc_details.isVisible()
    reread = None
    for btn in page.findChildren(QPushButton):
        if btn.accessibleName() == "Relire le disque":
            reread = btn
            break
    assert reread is not None
    assert reread.maximumWidth() <= 280


def test_status_cleared_outside_archive(qapp, config, db) -> None:
    win = MainWindow(config, db)
    try:
        win.lbl_reader.setText("CD 17 pistes · environ 59 min")
        win.navigate_to(1)  # Bibliothèque
        assert "CD 17" not in win.lbl_reader.text()
        win.lbl_reader.setText("CD 17 pistes · environ 59 min")
        # Emission statut hors Archivage ignorée
        win.wizard.status_message.emit("CD 12 pistes · environ 40 min")
        assert win.stack.currentIndex() != NAV_ARCHIVE
        assert "CD 12" not in win.lbl_reader.text()
        win.navigate_to(NAV_ARCHIVE)
        win.wizard.status_message.emit("CD 12 pistes · environ 40 min")
        assert "CD 12" in win.lbl_reader.text()
    finally:
        win.close()
        win.deleteLater()
        qapp.processEvents()


def test_library_friendly_paths_and_cover_priority(qapp, config, db, tmp_path) -> None:
    album = tmp_path / "lib" / "Queen" / "1992 - Greatest Hits"
    album.mkdir(parents=True)
    (album / "cover.jpg").write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("d1", "m1", "Queen", "Greatest Hits", 1992, str(album), "imported", now),
    )
    conn.commit()
    page = LibraryPage(config, db)
    page.refresh()
    page.resize(QSize(820, 640))
    qapp.processEvents()
    assert page.list.iconSize().width() >= 96
    lay = page.layout()
    assert lay.stretch(lay.indexOf(page.list)) >= 3
    root_txt = page.lbl_root.text()
    assert "Albums FLAC locaux" in root_txt
    # libellé court (pas le chemin absolu complet en clair dominant)
    assert friendly_path_label(str(config.library_root)) in root_txt or "lib" in root_txt.lower()
    page.list.setCurrentRow(0)
    qapp.processEvents()
    detail = page.lbl_detail.text()
    assert "Dossier :" in detail
    assert "Queen" in detail or "Greatest Hits" in detail
    assert str(album) not in detail


def test_settings_scroll_area(qapp, config) -> None:
    page = SettingsPage(config)
    scrolls = page.findChildren(QScrollArea)
    assert scrolls, "Paramètres doit avoir une QScrollArea"
    assert scrolls[0].widgetResizable()
    assert scrolls[0].accessibleName()


def test_settings_library_destination_persists_and_reaches_workflow(
    qapp, config, db, tmp_path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QMessageBox

    data_dir = tmp_path / "app-data"
    selected_root = tmp_path / "Permanent Music Library"
    monkeypatch.setenv("AVM_DATA_DIR", str(data_dir))
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    win = MainWindow(config, db)
    win.page_settings.edit_library.setText(str(selected_root))

    win.page_settings._save()  # noqa: SLF001

    assert load_config().library_root == str(selected_root)
    assert win.wizard._config.library_root == str(selected_root)  # noqa: SLF001
    assert win.page_library._config.library_root == str(selected_root)  # noqa: SLF001
    assert not selected_root.exists()


def test_wizard_displays_normal_destination_and_publish_result(qapp, config, db, tmp_path) -> None:
    wizard = ArchiveWizardPage(config, db)
    wizard._sheet = make_approvable_sheet()  # noqa: SLF001
    wizard._refresh_w4_preview()  # noqa: SLF001
    assert "Mode : archivage CD normal" in wizard.lbl_w4_recap.text()
    assert str(config.library_root) in wizard.lbl_w4_recap.text()

    album_dir = Path(config.library_root) / "Demo Artist" / "Demo Album (1999)"
    report = ArchiveJobReport(
        job_id="job-normal",
        workdir=tmp_path / "jobs" / "job-normal",
        mode=JobMode.NORMAL,
        metadata_id=wizard.sheet().id,
        publish=PublishResult(
            published=True,
            policy=CollisionPolicy.RENAME,
            album_dir=album_dir,
        ),
        state="Completed",
    )
    wizard._on_archive_finished(report)  # noqa: SLF001
    details = wizard.txt_done.toPlainText()
    assert "Publication et indexation SQLite : réussies" in details
    assert str(config.library_root) in details
    assert str(album_dir) in details
    assert "Album ajouté à votre bibliothèque" in wizard.lbl_done.text()

    report.publish = None
    report.state = "AwaitingPublishConfirmation"
    wizard._on_archive_finished(report)  # noqa: SLF001
    assert "Publication : non effectuée" in wizard.txt_done.toPlainText()
    assert "Album ajouté à votre bibliothèque" not in wizard.lbl_done.text()


def test_technical_rip_result_explicitly_says_unpublished(qapp, config, db, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QMessageBox

    messages = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _parent, _title, message: messages.append(message)
    )
    win = MainWindow(config, db)
    report = RipJobReport(
        job_id="job-test",
        workdir=tmp_path / "jobs" / "job-test" / "rip",
        rip=RipResult(
            success=True,
            cancelled=False,
            returncode=0,
            argv=(),
            stdout="",
            stderr="",
            flac_files=[tmp_path / "jobs" / "job-test" / "rip" / "01.flac"],
        ),
        mode=JobMode.TECHNICAL_TEST,
    )

    win._on_tech_finished(report)  # noqa: SLF001

    assert "technical_test" in messages[0]
    assert "Publication bibliothèque : aucune" in messages[0]
    assert "archivé" not in messages[0].casefold()


def test_history_detail_uses_friendly_paths(qapp, db, tmp_path) -> None:
    album = tmp_path / "Music" / "Queen" / "GH"
    album.mkdir(parents=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    conn.execute(
        """
        INSERT INTO jobs(
            id, state, step, workdir, started_at, updated_at, finished_at,
            error_summary, mode, publish_allowed, library_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "o1",
            "Completed",
            "Completed",
            None,
            now,
            now,
            now,
            None,
            "normal",
            1,
            str(album),
        ),
    )
    conn.commit()
    page = HistoryPage(db)
    page.refresh()
    page.select_row(0)
    text = page.txt_detail.toPlainText()
    assert "Album publié :" in text
    assert "Queen" in text or "GH" in text
    # chemin absolu complet pas dominant dans le corps
    assert str(album) not in text or friendly_path_label(str(album)) in text
    tip = page.txt_detail.toolTip()
    assert str(album) in tip or tip == ""
