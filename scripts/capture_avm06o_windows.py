"""Captures Windows réelles AVM-06O (finitions UX/UI) — pas offscreen."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from audio_video_manager.config import AppConfig  # noqa: E402
from audio_video_manager.storage import Database  # noqa: E402
from audio_video_manager.ui.main_window import MainWindow, NAV_ARCHIVE  # noqa: E402
from audio_video_manager.ui.theme import apply_app_style  # noqa: E402

OUT = ROOT / "docs" / "ux" / "reports" / "assets"


def _seed(db: Database, lib: Path, tmp: Path) -> Path:
    album = lib / "Queen" / "1992 - Greatest Hits"
    album.mkdir(parents=True, exist_ok=True)
    (album / "cover.jpg").write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    )
    (album / "01 - Track.flac").write_bytes(b"flac")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    cur = conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("demo.disc.id", "mbid-a", "Queen", "Greatest Hits", 1992, str(album), "imported", now),
    )
    rid = cur.lastrowid
    conn.execute(
        "INSERT INTO tracks(release_id, number, title, path, duration_ms, flac_ok) VALUES (?,?,?,?,?,?)",
        (rid, 1, "We Will Rock You", str(album / "01 - Track.flac"), 122000, 1),
    )
    job_tmp = tmp / "job_tmp"
    job_tmp.mkdir(parents=True, exist_ok=True)
    for jid, state, err, libp, wd in (
        ("o-comp", "Completed", None, str(album), None),
        ("o-fail", "Failed", "freaccmd returncode=4294967293", None, str(job_tmp)),
    ):
        conn.execute(
            """
            INSERT INTO jobs(id, state, step, workdir, started_at, updated_at, finished_at,
                error_summary, mode, publish_allowed, library_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (jid, state, state, wd, now, now, now, err, "normal", 1, libp),
        )
    conn.commit()
    return album


def _grab(win: MainWindow, name: str) -> Path:
    path = OUT / name
    win.grab().save(str(path), "PNG")
    print("wrote", path, win.width(), "x", win.height())
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    apply_app_style(app)
    platform = QApplication.platformName()
    style_name = app.style().objectName() or app.style().metaObject().className()
    print("platform=", platform, "style=", style_name)
    if platform == "offscreen":
        print("REFUS: capture exige plateforme windows (pas offscreen)")
        return 2

    tmp = ROOT / ".capture_avm06o"
    tmp.mkdir(exist_ok=True)
    lib = tmp / "lib"
    lib.mkdir(exist_ok=True)
    db_path = tmp / "cap.sqlite3"
    if db_path.exists():
        db_path.unlink()
    db = Database(db_path)
    db.initialize()
    _seed(db, lib, tmp)

    config = AppConfig(
        library_root=str(lib.resolve()),
        jobs_dir=str(tmp / "jobs"),
        log_dir=str(tmp / "logs"),
        freaccmd_path=r"C:\Program Files\freac\freaccmd.exe",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )
    win = MainWindow(config, db)
    win.setWindowTitle(f"AVM-06O ({platform}/{style_name})")
    win.show()
    app.processEvents()

    sizes = (
        ("1120", QSize(1120, 740)),
        ("980", QSize(980, 680)),
        ("820", QSize(820, 640)),
    )

    # --- Archivage W1 (Disc ID replié) ---
    win.navigate_to(NAV_ARCHIVE)
    app.processEvents()
    wiz = win.wizard
    wiz.lbl_disc.setText("CD détecté — 17 pistes · environ 59 minutes")
    wiz.lbl_disc_details.setText("Disc ID : abcd1234.efgh")
    wiz.btn_tech_details.setChecked(False)
    wiz.lbl_disc_details.hide()
    app.processEvents()
    for tag, size in sizes:
        win.resize(size)
        app.processEvents()
        _grab(win, f"avm06o-archive-w1-{tag}.png")
    tech_default = wiz.btn_tech_details.isChecked()
    wiz.btn_tech_details.setChecked(True)
    app.processEvents()
    win.resize(QSize(1120, 740))
    app.processEvents()
    _grab(win, "avm06o-archive-w1-tech-details.png")
    wiz.btn_tech_details.setChecked(False)
    app.processEvents()

    # Statut CD ne fuit pas hors Archivage
    win.lbl_reader.setText("CD 17 pistes · environ 59 min")
    win.navigate_to(1)
    app.processEvents()
    status_after = win.lbl_reader.text()
    print("status_after_leave_archive=", status_after)

    # --- Bibliothèque ---
    win.page_library.refresh()
    app.processEvents()
    if win.page_library.list.count():
        win.page_library.list.setCurrentRow(0)
    app.processEvents()
    for tag, size in sizes:
        win.resize(size)
        app.processEvents()
        _grab(win, f"avm06o-library-{tag}.png")

    win.showMaximized()
    app.processEvents()
    _grab(win, "avm06o-library-maximized.png")
    win.showNormal()
    app.processEvents()

    # --- Historique (chemins amicaux) ---
    win.navigate_to(2)
    app.processEvents()
    win.page_history.refresh()
    if win.page_history.list.count():
        win.page_history.select_row(0)
    app.processEvents()
    win.resize(QSize(1120, 740))
    app.processEvents()
    _grab(win, "avm06o-history-1120.png")

    # --- Paramètres (scroll) ---
    win.navigate_to(3)
    app.processEvents()
    for tag, size in (("1120", QSize(1120, 740)), ("820", QSize(820, 640))):
        win.resize(size)
        app.processEvents()
        _grab(win, f"avm06o-settings-{tag}.png")
    # Scroll bas pour Avancé
    scrolls = win.page_settings.findChildren(
        __import__("PySide6.QtWidgets", fromlist=["QScrollArea"]).QScrollArea
    )
    if scrolls:
        bar = scrolls[0].verticalScrollBar()
        bar.setValue(bar.maximum())
        app.processEvents()
        _grab(win, "avm06o-settings-scrolled.png")

    meta = OUT.parent / "avm06o-capture-meta.txt"
    meta.write_text(
        f"platform={platform}\n"
        f"style={style_name}\n"
        f"status_after_leave_archive={status_after}\n"
        f"library_root_label={win.page_library.lbl_root.text()}\n"
        f"w1_tech_default_checked={tech_default}\n"
        f"captured_at={datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )
    print("meta", meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
