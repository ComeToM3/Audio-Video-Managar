"""AVM-07B — repro fermeture pendant worker (simulé) : ancien vs nouveau cycle de vie."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".capture_avm07a"
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable


OLD = r'''
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QMainWindow

class W(QObject):
    finished = Signal(object)
    failed = Signal(str)
    def __init__(self):
        super().__init__()
        self._c = False
    def cancel(self):
        self._c = True
    @Slot()
    def run(self):
        for _ in range(500):
            if self._c:
                self.failed.emit("c"); return
            time.sleep(0.02)
        self.finished.emit("ok")

app = QApplication([])
win = QMainWindow()
win.show()
w = W()
# ANTI-PATTERN : parent = fenêtre
t = QThread(win)
w.moveToThread(t)
t.started.connect(w.run)
w.finished.connect(t.quit)
w.failed.connect(t.quit)
t.finished.connect(w.deleteLater)
t.start()
time.sleep(0.2)
# Destruction fenêtre alors que le thread tourne (crash réel 17:39)
win.close()
win.deleteLater()
app.processEvents()
time.sleep(0.1)
# Pas d attente — reproduit Destroyed while thread is still running
sys.exit(0)
'''

NEW = r'''
import os, sys, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication, QMainWindow
from audio_video_manager.ui.thread_lifecycle import attach_worker_thread, shutdown_worker_thread

class W(QObject):
    finished = Signal(object)
    failed = Signal(str)
    def __init__(self):
        super().__init__()
        self._c = False
    def cancel(self):
        self._c = True
    @Slot()
    def run(self):
        for _ in range(500):
            if self._c:
                self.failed.emit("c"); return
            time.sleep(0.02)
        self.finished.emit("ok")

app = QApplication([])
win = QMainWindow()
win.show()
w = W()
t = attach_worker_thread(w)
t.start()
time.sleep(0.2)
ok = shutdown_worker_thread(t, w, timeout_ms=5000)
win.close()
win.deleteLater()
app.processEvents()
sys.exit(0 if ok else 2)
'''


def run_snippet(name: str, code: str, reps: int = 5) -> list[dict]:
    rows = []
    for i in range(reps):
        script = OUT / f"_repro_{name}_{i}.py"
        script.write_text(code, encoding="utf-8")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        t0 = time.perf_counter()
        p = subprocess.run(
            [PY, "-X", "faulthandler", str(script)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
        )
        u = p.returncode & 0xFFFFFFFF
        klass = "OK"
        if u == 0xC0000005:
            klass = "ACCESS_VIOLATION"
        elif u == 0xC0000409:
            klass = "STACK_BUFFER_OVERRUN"
        elif p.returncode != 0:
            klass = f"OTHER_{u:#x}"
        row = {
            "name": f"{name}_r{i+1}",
            "rc": p.returncode,
            "u32": u,
            "class": klass,
            "seconds": round(time.perf_counter() - t0, 3),
            "stderr_tail": (p.stderr or "")[-400:],
        }
        print(row["class"], row["name"], "rc=", row["rc"], flush=True)
        rows.append(row)
    return rows


def main() -> int:
    rows = []
    rows.extend(run_snippet("old_parent_destroy", OLD, 5))
    rows.extend(run_snippet("new_shutdown", NEW, 5))
    path = OUT / "repro_qthread_07b.json"
    path.write_text(
        json.dumps(
            {"captured_at": datetime.now(timezone.utc).isoformat(), "rows": rows},
            indent=2,
        ),
        encoding="utf-8",
    )
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
