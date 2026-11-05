"""Captures Windows — Bibliothèque hybride QML dans MainWindow (AVM-08B)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ["AVM_LIBRARY_UI"] = "qml"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from audio_video_manager.config import AppConfig  # noqa: E402
from audio_video_manager.storage import Database  # noqa: E402
from audio_video_manager.ui.main_window import MainWindow  # noqa: E402
from audio_video_manager.ui.theme import apply_app_style  # noqa: E402

OUT = ROOT / "docs" / "ux" / "reports" / "assets"


def _seed(db: Database, lib: Path) -> None:
    album = lib / "Queen" / "1992 - Greatest Hits"
    album.mkdir(parents=True, exist_ok=True)
    # Réutilise cover réelle si présente dans biblio utilisateur
    src = Path(r"C:\Users\ComeToM3\Music\AVM-06C-Test-Library\Queen\Greatest Hits (1992)\cover.jpg")
    if src.is_file():
        (album / "cover.jpg").write_bytes(src.read_bytes())
    else:
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
        ("demo", "mb", "Queen", "Greatest Hits", 1992, str(album), "imported", now),
    )
    rid = cur.lastrowid
    conn.execute(
        "INSERT INTO tracks(release_id, number, title, path, duration_ms, flac_ok) VALUES (?,?,?,?,?,?)",
        (rid, 1, "We Will Rock You", str(album / "01.flac"), 122000, 1),
    )
    conn.commit()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    apply_app_style(app)
    platform = app.platformName()
    print("platform=", platform)
    if platform == "offscreen":
        return 2

    tmp = ROOT / ".capture_avm08b"
    tmp.mkdir(exist_ok=True)
    lib = tmp / "lib"
    lib.mkdir(exist_ok=True)
    dbp = tmp / "cap.sqlite3"
    if dbp.exists():
        dbp.unlink()
    db = Database(dbp)
    db.initialize()
    _seed(db, lib)

    cfg = AppConfig(
        library_root=str(lib),
        jobs_dir=str(tmp / "jobs"),
        log_dir=str(tmp / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
        library_ui_mode="qml",
    )
    win = MainWindow(cfg, db)
    win.setWindowTitle(f"AVM-08B hybrid ({platform})")
    win.show()
    app.processEvents()
    win.navigate_to(1)
    app.processEvents()
    host = win.page_library
    print("using_qml=", getattr(host, "using_qml", None))

    for tag, size in (
        ("1120", QSize(1120, 740)),
        ("980", QSize(980, 680)),
        ("820", QSize(820, 640)),
    ):
        win.resize(size)
        app.processEvents()
        path = OUT / f"avm08b-library-qml-{tag}.png"
        win.grab().save(str(path), "PNG")
        print("wrote", path)

    win.showMaximized()
    app.processEvents()
    path = OUT / "avm08b-library-qml-maximized.png"
    win.grab().save(str(path), "PNG")
    print("wrote", path, win.width(), "x", win.height())

    # Repli Widgets
    win.showNormal()
    win.resize(QSize(1120, 740))
    app.processEvents()
    if hasattr(host, "force_widgets_fallback"):
        host.force_widgets_fallback()
        app.processEvents()
        path = OUT / "avm08b-library-widgets-fallback-1120.png"
        win.grab().save(str(path), "PNG")
        print("wrote", path, "using_qml=", host.using_qml)

    meta = OUT.parent / "avm08b-capture-meta.txt"
    meta.write_text(
        f"platform={platform}\n"
        f"using_qml_initial=True\n"
        f"using_qml_after_fallback={getattr(host, 'using_qml', None)}\n"
        f"captured_at={datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )
    print("meta", meta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
