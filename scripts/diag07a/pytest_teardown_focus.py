"""AVM-07A — confirmer crash = teardown pytest (gc_collect_harder), pas les tests."""

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
PY = sys.executable


def run(name: str, argv: list[str], env: dict | None = None) -> dict:
    e = os.environ.copy()
    e["QT_QPA_PLATFORM"] = "offscreen"
    if env:
        e.update(env)
    t0 = time.perf_counter()
    p = subprocess.run(argv, cwd=str(ROOT), env=e, capture_output=True, text=True, errors="replace")
    dt = time.perf_counter() - t0
    u = p.returncode & 0xFFFFFFFF
    klass = "OK" if p.returncode == 0 else (
        "ACCESS_VIOLATION" if u == 0xC0000005 else f"OTHER_{u:#x}"
    )
    # Detect if tests finished before crash
    passed = "passed" in (p.stdout or "") or "[100%]" in (p.stdout or "")
    dots_done = "[100%]" in (p.stdout or "")
    gc_harder = "gc_collect_harder" in (p.stderr or "") or "gc_collect_harder" in (p.stdout or "")
    unconfigure = "_ensure_unconfigure" in (p.stderr or "") or "_ensure_unconfigure" in (p.stdout or "")
    row = {
        "name": name,
        "rc": p.returncode,
        "u32": u,
        "class": klass,
        "seconds": round(dt, 3),
        "dots_100": dots_done,
        "gc_collect_harder": gc_harder,
        "unconfigure": unconfigure,
        "stdout_tail": (p.stdout or "")[-800:],
        "stderr_tail": (p.stderr or "")[-1200:],
    }
    print(f"{klass:18} {name:45} 100%={dots_done} gc_harder={gc_harder}", flush=True)
    return row


def main() -> int:
    rows = []
    # Baseline crashing file
    rows.append(
        run(
            "ux06o_default",
            [PY, "-X", "faulthandler", "-m", "pytest", "tests/test_ux_06o.py", "-q", "--tb=no"],
        )
    )
    # Disable unraisableexception hook cleanup? not directly — try -p no:cacheprovider etc.
    rows.append(
        run(
            "ux06o_no_unraisable",
            [
                PY,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py",
                "-q",
                "--tb=no",
                "-p",
                "no:unraisableexception",
            ],
        )
    )
    rows.append(
        run(
            "ux06o_no_faulthandler_plugin",
            [
                PY,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py",
                "-q",
                "--tb=no",
                "-p",
                "no:faulthandler",
            ],
        )
    )
    # Only path label unit test (no widgets beyond imports?) — first test only
    rows.append(
        run(
            "ux06o_path_only",
            [
                PY,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py::test_friendly_path_label_last_segments",
                "-q",
                "--tb=no",
            ],
        )
    )
    rows.append(
        run(
            "ux06o_settings_only",
            [
                PY,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py::test_settings_scroll_area",
                "-q",
                "--tb=no",
            ],
        )
    )
    rows.append(
        run(
            "ux06o_status_mainwindow",
            [
                PY,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py::test_status_cleared_outside_archive",
                "-q",
                "--tb=no",
            ],
        )
    )
    rows.append(
        run(
            "ux06o_w1_disc",
            [
                PY,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py::test_w1_disc_id_hidden_by_default",
                "-q",
                "--tb=no",
            ],
        )
    )
    rows.append(
        run(
            "history06n_file",
            [PY, "-X", "faulthandler", "-m", "pytest", "tests/test_history_06n.py", "-q", "--tb=no"],
        )
    )
    rows.append(
        run(
            "shell_file",
            [PY, "-X", "faulthandler", "-m", "pytest", "tests/test_ui_shell.py", "-q", "--tb=no"],
        )
    )
    # JUnit then check — process still crashes after writing junit?
    junit = OUT / "teardown_junit.xml"
    rows.append(
        run(
            "ux06o_with_junit",
            [
                PY,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py",
                "-q",
                "--tb=no",
                f"--junitxml={junit}",
            ],
        )
    )
    junit_ok = junit.exists() and "failures=\"0\"" in junit.read_text(encoding="utf-8", errors="replace")
    rows.append({"name": "junit_wrote_pass", "junit_ok": junit_ok, "class": "META"})

    # Normal app entry: start and quit via timer (windows platform)
    harness = OUT / "_quit_harness.py"
    harness.write_text(
        """
import os, sys
from pathlib import Path
os.environ.pop('QT_QPA_PLATFORM', None)
ROOT = Path(r'''"""
        + str(ROOT).replace("\\", "\\\\")
        + """''')
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.theme import apply_app_style
tmp = ROOT / '.capture_avm07a' / 'harness'
tmp.mkdir(parents=True, exist_ok=True)
dbp = tmp / 'h.sqlite3'
if dbp.exists(): dbp.unlink()
app = QApplication([])
apply_app_style(app)
db = Database(dbp); db.initialize()
cfg = AppConfig(library_root=str(tmp/'lib'), jobs_dir=str(tmp/'jobs'), log_dir=str(tmp/'logs'),
                freaccmd_path=r'C:\\Program Files\\freac\\freaccmd.exe',
                preferred_release_country='CA', auto_approve_high_confidence=False)
(tmp/'lib').mkdir(exist_ok=True)
win = MainWindow(cfg, db)
win.show()
def _done():
    win.close(); db.close(); app.quit()
QTimer.singleShot(800, _done)
raise SystemExit(app.exec())
""",
        encoding="utf-8",
    )
    t0 = time.perf_counter()
    p = subprocess.run([PY, "-X", "faulthandler", str(harness)], cwd=str(ROOT))
    rows.append(
        {
            "name": "app_exec_quit_timer",
            "rc": p.returncode,
            "u32": p.returncode & 0xFFFFFFFF,
            "class": "OK" if p.returncode == 0 else (
                "ACCESS_VIOLATION" if (p.returncode & 0xFFFFFFFF) == 0xC0000005 else "OTHER"
            ),
            "seconds": round(time.perf_counter() - t0, 3),
        }
    )
    print(rows[-1], flush=True)

    # Repeat app exec 5x as separate processes
    for i in range(5):
        t0 = time.perf_counter()
        p = subprocess.run([PY, "-X", "faulthandler", str(harness)], cwd=str(ROOT))
        rows.append(
            {
                "name": f"app_exec_proc_r{i+1}",
                "rc": p.returncode,
                "class": "OK" if p.returncode == 0 else (
                    "ACCESS_VIOLATION" if (p.returncode & 0xFFFFFFFF) == 0xC0000005 else "OTHER"
                ),
                "seconds": round(time.perf_counter() - t0, 3),
            }
        )
        print(rows[-1], flush=True)

    path = OUT / "teardown_focus.json"
    path.write_text(
        json.dumps({"captured_at": datetime.now(timezone.utc).isoformat(), "rows": rows}, indent=2),
        encoding="utf-8",
    )
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
