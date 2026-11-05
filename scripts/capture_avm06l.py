"""Captures avant/après AVM-06L (Fusion, offscreen OK)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize, Qt  # noqa: E402
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
    # Minimal JPEG
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
        ("disc", "mb", "Queen", "Greatest Hits", 1992, str(album), "imported", now),
    )
    rid = cur.lastrowid
    conn.execute(
        "INSERT INTO tracks(release_id, number, title, path, duration_ms, flac_ok) VALUES (?,?,?,?,?,?)",
        (rid, 1, "We Will Rock You", str(album / "01 - Track.flac"), 122000, 1),
    )
    for state, err in (
        ("Completed", None),
        ("Failed", "Extraction interrompue (exemple)"),
    ):
        jid = f"cap-{state[:4]}"
        conn.execute(
            """
            INSERT INTO jobs(id, state, step, workdir, started_at, updated_at, finished_at,
                error_summary, mode, publish_allowed, library_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                jid,
                state,
                state,
                str(ROOT / "tmp_job") if state == "Failed" else None,
                now,
                now,
                now,
                err,
                "normal",
                1,
                str(album) if state == "Completed" else None,
            ),
        )
    conn.commit()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    apply_app_style(app)

    tmp = ROOT / ".capture_avm06l"
    tmp.mkdir(exist_ok=True)
    lib = tmp / "lib"
    lib.mkdir(exist_ok=True)
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
    win.resize(1120, 740)
    win.show()
    app.processEvents()

    shots = [
        ("avm06l-archive.png", 0),
        ("avm06l-library.png", 1),
        ("avm06l-history.png", 2),
    ]
    for name, idx in shots:
        win.navigate_to(idx)
        app.processEvents()
        # Sélection utile
        if idx == 1 and win.page_library.list.count():
            win.page_library.list.setCurrentRow(0)
        if idx == 2 and win.page_history.table.rowCount():
            win.page_history.table.selectRow(0)
        app.processEvents()
        path = OUT / name
        win.grab().save(str(path), "PNG")
        print("wrote", path)

    # Mode étroit
    old = QSize(1120, 740)
    new = QSize(NARROW_BREAKPOINT - 60, 700)
    win.resize(new)
    win.resizeEvent(QResizeEvent(new, old))
    win.navigate_to(1)
    app.processEvents()
    narrow = OUT / "avm06l-shell-narrow.png"
    win.grab().save(str(narrow), "PNG")
    print("wrote", narrow)

    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
