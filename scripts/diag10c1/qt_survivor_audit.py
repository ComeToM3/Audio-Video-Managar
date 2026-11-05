#!/usr/bin/env python3
"""AVM-10C.1 — audit QObject / QThread survivants après teardown (sans os._exit)."""

from __future__ import annotations

import gc
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".ci" / "avm10c1-survivors.json"

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ["AVM_QT_SAFE_EXIT"] = "0"


def _alive_qobjects() -> list[dict]:
    from PySide6.QtCore import QObject, QThread
    from shiboken6 import isValid

    rows = []
    for obj in gc.get_objects():
        try:
            if not isinstance(obj, QObject):
                continue
            if not isValid(obj):
                continue
            name = type(obj).__name__
            info: dict = {
                "type": name,
                "objectName": "",
                "thread": None,
                "running": None,
            }
            try:
                info["objectName"] = obj.objectName() or ""
            except RuntimeError:
                continue
            if isinstance(obj, QThread):
                try:
                    info["running"] = bool(obj.isRunning())
                    info["thread"] = "self"
                except RuntimeError:
                    pass
            rows.append(info)
        except Exception:  # noqa: BLE001
            continue
    return rows


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from audio_video_manager.config import AppConfig
    from audio_video_manager.storage import Database
    from audio_video_manager.ui.main_window import MainWindow
    from audio_video_manager.ui.theme import apply_app_style
    from tests.qt_support import shutdown_tracked_widgets, track_widget

    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_style(app)
    tmp = Path(tempfile.mkdtemp(prefix="avm10c1_surv_"))
    db = Database(tmp / "s.sqlite3")
    db.initialize()
    cfg = AppConfig(
        library_root=str(tmp / "lib"),
        jobs_dir=str(tmp / "jobs"),
        log_dir=str(tmp / "logs"),
        library_ui_mode="qml",
    )
    win = track_widget(MainWindow(cfg, db))
    win.show()
    for row in (0, 1, 0, 2, 1):
        win.navigate_to(row)
        app.processEvents()
    before_close = len(_alive_qobjects())
    win.close()
    app.processEvents()
    shutdown_tracked_widgets()
    app.processEvents()
    # Intentionally NO gc.collect() — known crash trigger
    after_soft = _alive_qobjects()
    running_threads = [r for r in after_soft if r.get("running") is True]
    qml_like = [
        r
        for r in after_soft
        if "Quick" in r["type"] or "Qml" in r["type"] or "Engine" in r["type"]
    ]
    payload = {
        "before_close_count": before_close,
        "after_soft_teardown_count": len(after_soft),
        "running_qthreads": running_threads,
        "qml_related_survivors_sample": qml_like[:30],
        "survivor_types_top": {},
    }
    from collections import Counter

    payload["survivor_types_top"] = dict(Counter(r["type"] for r in after_soft).most_common(25))
    db.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    # Natural return — do not os._exit
    return 0 if not running_threads else 3


if __name__ == "__main__":
    raise SystemExit(main())
