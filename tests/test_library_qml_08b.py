"""AVM-08B — Bibliothèque hybride QML + repli Widgets."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtWidgets import QApplication

from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.qml.library_bridge import LibraryBridge
from audio_video_manager.ui.sections.library_host import LibraryHost, resolve_library_ui_mode


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
        library_ui_mode="qml",
    )


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "lib08b.sqlite3")
    database.initialize()
    yield database
    database.close()


def _seed(db: Database, album: Path) -> None:
    album.mkdir(parents=True, exist_ok=True)
    (album / "cover.jpg").write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    )
    (album / "01.flac").write_bytes(b"flac")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    cur = conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("d08b", "m", "Queen", "Greatest Hits", 1992, str(album), "imported", now),
    )
    rid = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO tracks(release_id, number, title, path, duration_ms, flac_ok) VALUES (?,?,?,?,?,?)",
        (rid, 1, "We Will Rock You", str(album / "01.flac"), 122000, 1),
    )
    conn.commit()


def test_resolve_mode_env_and_config(config, monkeypatch) -> None:
    monkeypatch.delenv("AVM_LIBRARY_UI", raising=False)
    default_config = AppConfig()
    assert default_config.library_ui_mode == "widgets"
    assert resolve_library_ui_mode(default_config) == "widgets"
    config.library_ui_mode = "qml"
    assert resolve_library_ui_mode(config) == "qml"
    config.library_ui_mode = "widgets"
    assert resolve_library_ui_mode(config) == "widgets"
    monkeypatch.setenv("AVM_LIBRARY_UI", "widgets")
    config.library_ui_mode = "qml"
    assert resolve_library_ui_mode(config) == "widgets"
    monkeypatch.setenv("AVM_LIBRARY_UI", "qml")
    config.library_ui_mode = "widgets"
    assert resolve_library_ui_mode(config) == "qml"


def test_bridge_loads_shared_db(qapp, config, db, tmp_path) -> None:
    album = Path(config.library_root) / "Queen" / "GH"
    _seed(db, album)
    bridge = LibraryBridge(db)
    assert bridge.albumCount() == 1
    bridge.selectRow(0)
    assert bridge.selectedArtist == "Queen"
    assert bridge.hasSelection
    bridge.search("zzz")
    assert bridge.albumCount() == 0
    bridge.search("")
    assert bridge.albumCount() == 1
    # refresh sans nouvelle Database
    bridge.refresh()
    assert bridge.albumCount() == 1


def test_host_fallback_widgets(qapp, config, db, tmp_path) -> None:
    _seed(db, Path(config.library_root) / "Q" / "A")
    config.library_ui_mode = "widgets"
    host = LibraryHost(config, db)
    assert not host.using_qml
    host.refresh()
    assert host.list.count() == 1
    host.force_widgets_fallback()
    assert not host.using_qml


def test_host_toggle_and_api(qapp, config, db, tmp_path) -> None:
    _seed(db, Path(config.library_root) / "Q" / "B")
    host = LibraryHost(config, db)
    host.refresh()
    # API compat
    assert host.list.count() >= 1
    # Repli explicite toujours possible
    host.force_widgets_fallback()
    assert host.widgets_page.list.count() >= 1
    # Tentative retour QML (peut échouer en offscreen — alors rester widgets)
    host._toggle_mode()  # noqa: SLF001
    host.refresh()
    assert host.list.count() >= 1


def test_mainwindow_library_refresh_signal(qapp, config, db, tmp_path) -> None:
    _seed(db, Path(config.library_root) / "Q" / "C")
    win = MainWindow(config, db)
    assert isinstance(win.page_library, LibraryHost)
    win.page_library.refresh()
    n0 = win.page_library.list.count()
    # Simule publication → signal wizard
    win.wizard.library_changed.emit()
    assert win.page_library.list.count() == n0
    win.navigate_to(1)
    assert win.current_section() == 1
