#!/usr/bin/env python3
"""AVM-10C.1 — cycles app Windows réelle (platform=windows), fermeture normale.

Sans os._exit. Navigue Widgets + bibliothèque (QML si dispo) puis close().
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".ci" / "avm10c1-app-lifecycle.json"

# Ne pas forcer offscreen — Windows natif
os.environ.pop("QT_QPA_PLATFORM", None)
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from audio_video_manager.config import AppConfig
    from audio_video_manager.storage import Database
    from audio_video_manager.ui.main_window import MainWindow
    from audio_video_manager.ui.theme import apply_app_style

    cycles = int(os.environ.get("AVM_10C1_CYCLES", "5"))
    results = []
    tmp = Path(tempfile.mkdtemp(prefix="avm10c1_"))
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_style(app)

    for i in range(cycles):
        entry = {"cycle": i, "ok": False, "error": None}
        try:
            db = Database(tmp / f"c{i}.sqlite3")
            db.initialize()
            cfg = AppConfig(
                library_root=str(tmp / "lib"),
                jobs_dir=str(tmp / "jobs"),
                log_dir=str(tmp / "logs"),
                library_ui_mode="qml",
            )
            win = MainWindow(cfg, db)
            win.show()
            app.processEvents()
            # Navigation sections
            for row in (1, 0, 2, 3, 1, 0):
                win.navigate_to(row)
                app.processEvents()
            # Fermeture normale (closeEvent) — pas os._exit
            win.close()
            app.processEvents()
            win.deleteLater()
            app.processEvents()
            db.close()
            entry["ok"] = True
        except Exception as exc:  # noqa: BLE001
            entry["error"] = f"{exc}\n{traceback.format_exc()}"
        results.append(entry)

    # Quitter la boucle d’événements proprement
    QTimer.singleShot(0, app.quit)
    code = app.exec()
    # Fin de process normale (return) — pas os._exit
    payload = {
        "platform_env": os.environ.get("QT_QPA_PLATFORM"),
        "cycles": cycles,
        "app_exec_code": int(code),
        "results": results,
        "all_ok": all(r["ok"] for r in results) and code == 0,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
