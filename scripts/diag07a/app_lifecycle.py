"""AVM-07A — cycles ouverture/fermeture application normale (pas d'extraction)."""

from __future__ import annotations

import faulthandler
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

faulthandler.enable(all_threads=True)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".capture_avm07a"
OUT.mkdir(parents=True, exist_ok=True)

# Application normale : jamais offscreen
os.environ.pop("QT_QPA_PLATFORM", None)


def _one_cycle(cycle: int) -> dict:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from audio_video_manager.config import AppConfig
    from audio_video_manager.storage import Database
    from audio_video_manager.ui.main_window import MainWindow, NAV_ARCHIVE
    from audio_video_manager.ui.theme import apply_app_style

    t0 = time.perf_counter()
    note = {"cycle": cycle, "events": []}
    tmp = OUT / f"app_cycle_{cycle}"
    tmp.mkdir(exist_ok=True)
    lib = tmp / "lib"
    lib.mkdir(exist_ok=True)
    db_path = tmp / "db.sqlite3"
    if db_path.exists():
        db_path.unlink()

    app = QApplication.instance() or QApplication([])
    apply_app_style(app)
    note["platform"] = QApplication.platformName()
    note["style"] = app.style().objectName() or app.style().metaObject().className()

    db = Database(db_path)
    db.initialize()
    config = AppConfig(
        library_root=str(lib),
        jobs_dir=str(tmp / "jobs"),
        log_dir=str(tmp / "logs"),
        freaccmd_path=r"C:\Program Files\freac\freaccmd.exe",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )
    win = MainWindow(config, db)
    win.show()
    app.processEvents()
    note["events"].append("shown")

    # Navigation 0→1→2→3→0
    for idx in (1, 2, 3, NAV_ARCHIVE, 1):
        win.navigate_to(idx)
        app.processEvents()
        note["events"].append(f"nav_{idx}")

    win.close()
    app.processEvents()
    win.deleteLater()
    app.processEvents()
    db.close()
    note["events"].append("closed")
    note["seconds"] = round(time.perf_counter() - t0, 3)
    note["status"] = "ok"
    return note


def main() -> int:
    results = []
    n = 5
    for i in range(1, n + 1):
        print(f"=== app cycle {i}/{n} ===", flush=True)
        try:
            results.append(_one_cycle(i))
            print("OK", results[-1]["seconds"], "s", results[-1].get("platform"), flush=True)
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "cycle": i,
                    "status": "exception",
                    "error": str(exc),
                    "trace": traceback.format_exc(),
                }
            )
            print("EXC", exc, flush=True)
            break

    # Quitter proprement QApplication unique
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.quit()
        app.processEvents()

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "cycles": results,
        "all_ok": all(r.get("status") == "ok" for r in results),
    }
    path = OUT / "app_lifecycle.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", path, "all_ok=", payload["all_ok"])
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
