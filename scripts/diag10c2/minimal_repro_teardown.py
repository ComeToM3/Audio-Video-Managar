#!/usr/bin/env python3
"""AVM-10C.2 — reproductions minimales (fixture vs app vs Shiboken).

Scénarios (sous-processus) :
  A  MainWindow show/close + shutdown_ui + deleteLater + drain  → return naturel
  B  ArchiveWizardPage sans teardown explicite                 → return naturel
  C  comme B + qt_session_cleanup()                            → return naturel
  D  MainWindow + gc.collect() forcé (déclencheur connu)       → attendu crash

Usage:
  python scripts/diag10c2/minimal_repro_teardown.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".ci" / "avm10c2-minimal-repro.json"

SCENARIO = r"""
import gc, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, r"{root}")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
from PySide6.QtWidgets import QApplication
from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage
from audio_video_manager.ui.theme import apply_app_style
from tests.qt_support import dispose_widget, drain_deferred_deletes, qt_session_cleanup

mode = sys.argv[1]
app = QApplication.instance() or QApplication([])
apply_app_style(app)
tmp = Path(tempfile.mkdtemp(prefix="avm10c2_"))
db = Database(tmp / "t.sqlite3"); db.initialize()
cfg = AppConfig(library_root=str(tmp/"lib"), jobs_dir=str(tmp/"jobs"), log_dir=str(tmp/"logs"))

if mode == "A":
    win = MainWindow(cfg, db)
    win.show(); app.processEvents(); win.navigate_to(1); app.processEvents()
    dispose_widget(win); drain_deferred_deletes(); db.close()
elif mode == "B":
    page = ArchiveWizardPage(cfg, db)
    page.show(); app.processEvents()
    # volontairement pas de dispose — simule fixture oubliée
    db.close()
elif mode == "C":
    page = ArchiveWizardPage(cfg, db)
    page.show(); app.processEvents()
    del page
    qt_session_cleanup(); db.close()
elif mode == "D":
    win = MainWindow(cfg, db)
    win.show(); app.processEvents()
    # close soft sans deleteLater, puis GC forcé (Mode A)
    win.close(); app.processEvents()
    gc.collect()
    db.close()
else:
    raise SystemExit(2)
raise SystemExit(0)
"""


def run_mode(mode: str) -> dict:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    env["PYTHONFAULTHANDLER"] = "1"
    proc = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", SCENARIO.format(root=str(ROOT)), mode],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    rc = int(proc.returncode)
    u = rc & 0xFFFFFFFF
    kind = "PASS"
    if u == 0xC0000005 or rc in (-1073741819, 139):
        kind = "NATIVE_0xC0000005"
    elif u == 0xC0000409:
        kind = "NATIVE_0xC0000409"
    elif rc != 0:
        kind = f"FAIL_rc_{rc}"
    err = (proc.stderr or "")[-400:]
    return {"mode": mode, "returncode": rc, "classification": kind, "stderr_tail": err}


def main() -> int:
    results = [run_mode(m) for m in ("A", "B", "C", "D")]
    payload = {
        "results": results,
        "interpretation": {
            "A": "teardown app correct → doit PASS",
            "B": "fixture oubliée → crash ou Abort possible",
            "C": "cleanup central répare B → doit PASS",
            "D": "gc.collect forcé → crash attendu (pas un bug métier)",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    # Succès du script diag si A et C passent et D crash (prouve le déclencheur)
    a_ok = results[0]["returncode"] == 0
    c_ok = results[2]["returncode"] == 0
    return 0 if a_ok and c_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
