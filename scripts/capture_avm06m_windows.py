"""Captures Windows réelles AVM-06M (pas offscreen). Lecture seule UI."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Preuve Windows : ne jamais forcer offscreen
os.environ.pop("QT_QPA_PLATFORM", None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QResizeEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from audio_video_manager.config import AppConfig  # noqa: E402
from audio_video_manager.storage import Database  # noqa: E402
from audio_video_manager.ui.main_window import MainWindow, NARROW_BREAKPOINT  # noqa: E402
from audio_video_manager.ui.theme import apply_app_style  # noqa: E402

OUT = ROOT / "docs" / "ux" / "reports" / "assets"


def _seed(db: Database, lib: Path) -> None:
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
    # Album manquant
    conn.execute(
        """
        INSERT INTO releases(disc_id, mbid, album_artist, album, year, path, status, imported_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        ("other", "mb-other", "Ghost Artist", "Dossier disparu", 2001, str(lib / "gone" / "x"), "imported", now),
    )
    for state, err, libp, wd in (
        ("Completed", None, str(album), None),
        ("Failed", "Exemple d’échec (validation UX)", None, str(ROOT / ".capture_avm06m" / "job_tmp")),
        ("Abandoned", "Abandonné volontairement — fichiers non supprimés.", None, None),
    ):
        if wd:
            Path(wd).mkdir(parents=True, exist_ok=True)
        conn.execute(
            """
            INSERT INTO jobs(id, state, step, workdir, started_at, updated_at, finished_at,
                error_summary, mode, publish_allowed, library_path, disc_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"m06m-{state[:4]}",
                state,
                state,
                wd,
                now,
                now,
                now,
                err,
                "normal",
                1,
                libp,
                "demo.disc.id" if state == "Completed" else None,
            ),
        )
    conn.commit()


def _grab(win: MainWindow, name: str) -> Path:
    path = OUT / name
    win.grab().save(str(path), "PNG")
    print("wrote", path, "size", win.width(), "x", win.height(), "platform", QApplication.platformName())
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    apply_app_style(app)
    platform = QApplication.platformName()
    print("platformName=", platform)
    if platform == "offscreen":
        print("ERREUR: offscreen détecté — abort (preuve Windows requise)")
        return 2

    tmp = ROOT / ".capture_avm06m"
    tmp.mkdir(exist_ok=True)
    lib = tmp / "lib"
    lib.mkdir(exist_ok=True)
    db = Database(tmp / "cap.sqlite3")
    if db.path.exists():
        db.close()
        db.path.unlink(missing_ok=True)
        db = Database(tmp / "cap.sqlite3")
    db.initialize()
    _seed(db, lib)

    config = AppConfig(
        library_root=str(lib),
        jobs_dir=str(tmp / "jobs"),
        log_dir=str(tmp / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )
    win = MainWindow(config, db)
    win.setWindowTitle(f"AVM-06M validation ({platform})")
    win.resize(1120, 740)
    win.show()
    app.processEvents()

    # Large — Archivage
    win.navigate_to(0)
    app.processEvents()
    _grab(win, "avm06m-archive-1120.png")

    # Large — Bibliothèque
    win.navigate_to(1)
    app.processEvents()
    if win.page_library.list.count():
        win.page_library.list.setCurrentRow(0)
    app.processEvents()
    _grab(win, "avm06m-library-1120.png")

    # Large — Historique
    win.navigate_to(2)
    app.processEvents()
    if win.page_history.table.rowCount():
        win.page_history.table.selectRow(0)
    app.processEvents()
    _grab(win, "avm06m-history-1120.png")

    # Paramètres
    win.navigate_to(3)
    app.processEvents()
    _grab(win, "avm06m-settings-1120.png")

    # Intermédiaire
    old = QSize(1120, 740)
    mid = QSize(980, 680)
    win.resize(mid)
    win.resizeEvent(QResizeEvent(mid, old))
    win.navigate_to(1)
    app.processEvents()
    _grab(win, "avm06m-library-980.png")

    # Étroit (<900)
    nar = QSize(NARROW_BREAKPOINT - 80, 640)
    win.resize(nar)
    win.resizeEvent(QResizeEvent(nar, mid))
    win.navigate_to(0)
    app.processEvents()
    _grab(win, "avm06m-archive-narrow.png")
    win.navigate_to(1)
    app.processEvents()
    _grab(win, "avm06m-library-narrow.png")
    win.navigate_to(2)
    app.processEvents()
    if win.page_history.table.rowCount():
        win.page_history.table.selectRow(1)
    app.processEvents()
    _grab(win, "avm06m-history-narrow.png")

    # Maximisé (si possible)
    win.showMaximized()
    app.processEvents()
    win.navigate_to(1)
    app.processEvents()
    _grab(win, "avm06m-library-maximized.png")

    # Accessibilité — inventaire AccessibleName
    names = []
    for w in win.findChildren(object):
        try:
            an = w.accessibleName()
            if an:
                names.append(f"{type(w).__name__}: {an}")
        except Exception:
            pass
    acc_path = OUT.parent / "avm06m-accessible-names.txt"
    acc_path.write_text("\n".join(sorted(set(names))), encoding="utf-8")
    print("wrote", acc_path, "count", len(set(names)))

    # Focus ring smoke : Tab une fois sur wizard
    win.navigate_to(0)
    win.showNormal()
    win.resize(1120, 740)
    app.processEvents()
    win.wizard.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    _grab(win, "avm06m-archive-focus-tab.png")

    meta = OUT.parent / "avm06m-capture-meta.txt"
    meta.write_text(
        f"platform={platform}\n"
        f"style={app.style().objectName() or type(app.style()).__name__}\n"
        f"narrow_breakpoint={NARROW_BREAKPOINT}\n"
        f"qt={QApplication.instance().applicationName()}\n",
        encoding="utf-8",
    )
    print("wrote", meta)

    # Quitter sans bloquer (pas d'exec interactif)
    QTimer.singleShot(50, app.quit)
    app.exec()
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
