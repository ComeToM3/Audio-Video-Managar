"""Captures Windows réelles Historique AVM-06N (avant/après corrections)."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSize, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from audio_video_manager.config import AppConfig  # noqa: E402
from audio_video_manager.storage import Database  # noqa: E402
from audio_video_manager.ui.main_window import MainWindow  # noqa: E402
from audio_video_manager.ui.theme import apply_app_style  # noqa: E402

OUT = ROOT / "docs" / "ux" / "reports" / "assets"


def _seed(db: Database, lib: Path, tmp: Path) -> None:
    album = lib / "Queen" / "1992 - Greatest Hits"
    album.mkdir(parents=True, exist_ok=True)
    (album / "cover.jpg").write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = db.connect()
    job_tmp = tmp / "job_tmp"
    job_tmp.mkdir(parents=True, exist_ok=True)
    rows = [
        ("n-comp", "Completed", None, str(album), None),
        ("n-fail", "Failed", "freaccmd returncode=4294967293", None, str(job_tmp)),
        ("n-canc", "Cancelled", "Annulé par l’utilisateur.", None, str(job_tmp)),
        ("n-aban", "Abandoned", "Abandonné volontairement — fichiers non supprimés.", None, None),
    ]
    for jid, state, err, libp, wd in rows:
        conn.execute(
            """
            INSERT INTO jobs(id, state, step, workdir, started_at, updated_at, finished_at,
                error_summary, mode, publish_allowed, library_path)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (jid, state, state, wd, now, now, now, err, "normal", 1, libp),
        )
    conn.commit()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    apply_app_style(app)
    platform = QApplication.platformName()
    print("platform=", platform)
    if platform == "offscreen":
        return 2

    tmp = ROOT / ".capture_avm06n"
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
        library_root=str(lib),
        jobs_dir=str(tmp / "jobs"),
        log_dir=str(tmp / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )
    win = MainWindow(config, db)
    win.setWindowTitle(f"AVM-06N Historique ({platform})")
    win.show()
    app.processEvents()
    win.navigate_to(2)
    app.processEvents()
    hist = win.page_history
    hist.refresh()
    app.processEvents()

    for name, size in (
        ("avm06n-history-1120.png", QSize(1120, 740)),
        ("avm06n-history-980.png", QSize(980, 680)),
        ("avm06n-history-820.png", QSize(820, 640)),
    ):
        win.resize(size)
        app.processEvents()
        hist.refresh()
        app.processEvents()
        # Sélection 2ᵉ carte (échec) via API carte
        if hist.list.count() >= 2:
            hist.select_row(1)
        app.processEvents()
        path = OUT / name
        win.grab().save(str(path), "PNG")
        print("wrote", path, "w=", win.width(), "hbar_max=", hist.list.horizontalScrollBar().maximum())

    # Première carte (terminé)
    hist.select_row(0)
    app.processEvents()
    win.resize(QSize(1120, 740))
    app.processEvents()
    path = OUT / "avm06n-history-selected-completed.png"
    win.grab().save(str(path), "PNG")
    print("wrote", path)

    meta = OUT.parent / "avm06n-capture-meta.txt"
    meta.write_text(
        f"platform={platform}\n"
        f"resume_visible={hist.btn_resume.isVisible()}\n"
        f"selected={hist._selected.id if hist._selected else None}\n",  # noqa: SLF001
        encoding="utf-8",
    )
    print("wrote", meta)

    QTimer.singleShot(50, app.quit)
    app.exec()
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
