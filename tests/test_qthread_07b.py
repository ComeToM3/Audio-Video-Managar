"""AVM-07B — cycle de vie QThread (workers simulés, pas d’extraction physique)."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication, QMainWindow

from audio_video_manager.config import AppConfig
from audio_video_manager.storage import Database
from audio_video_manager.ui.main_window import MainWindow
from audio_video_manager.ui.thread_lifecycle import (
    attach_worker_thread,
    shutdown_worker_thread,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class SlowWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str, object)

    def __init__(self, hold_sec: float = 0.4) -> None:
        super().__init__()
        self._hold = hold_sec
        self._cancel = False
        self.ran = False
        self.cancelled_seen = False

    def cancel(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        self.ran = True
        t0 = time.monotonic()
        while time.monotonic() - t0 < self._hold:
            if self._cancel:
                self.cancelled_seen = True
                self.failed.emit("cancelled")
                return
            time.sleep(0.05)
        self.finished.emit({"ok": True})


def test_attach_worker_thread_has_no_widget_parent(qapp) -> None:
    win = QMainWindow()
    worker = SlowWorker(0.2)
    thread = attach_worker_thread(worker)
    assert thread.parent() is None
    assert worker.thread() is thread
    # Ancien anti-pattern : QThread(win) aurait parent=win
    bad = QThread(win)
    assert bad.parent() is win
    bad.deleteLater()
    win.close()


def test_shutdown_stops_running_worker(qapp) -> None:
    worker = SlowWorker(5.0)
    cleared = {"n": 0}

    def _clear() -> None:
        cleared["n"] += 1

    thread = attach_worker_thread(worker, on_cleared=_clear)
    thread.start()
    # Laisser démarrer
    for _ in range(50):
        qapp.processEvents()
        if worker.ran:
            break
        time.sleep(0.02)
    assert worker.ran
    assert thread.isRunning()
    ok = shutdown_worker_thread(thread, worker, timeout_ms=3000)
    assert ok is True
    assert not thread.isRunning()
    assert worker.cancelled_seen
    # finished/deleteLater asynchrones
    for _ in range(40):
        qapp.processEvents()
        time.sleep(0.02)
        if cleared["n"]:
            break
    assert cleared["n"] >= 1


def test_close_mainwindow_while_simulated_tech_running(qapp, tmp_path) -> None:
    """Repro scénario 07A/07B : fermeture pendant worker — ne doit pas AV."""
    lib = tmp_path / "lib"
    lib.mkdir()
    db = Database(tmp_path / "t.sqlite3")
    db.initialize()
    cfg = AppConfig(
        library_root=str(lib),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )
    win = MainWindow(cfg, db)
    worker = SlowWorker(3.0)
    thread = attach_worker_thread(
        worker,
        on_finished=lambda *_: None,
        on_failed=lambda *_: None,
        on_cleared=win._clear_tech,  # noqa: SLF001
    )
    win._tech_worker = worker  # noqa: SLF001
    win._tech_thread = thread  # noqa: SLF001
    thread.start()
    for _ in range(50):
        qapp.processEvents()
        if worker.ran:
            break
        time.sleep(0.02)
    assert thread.isRunning()
    # closeEvent demande confirmation — on appelle shutdown directement (chemin critique)
    ok = shutdown_worker_thread(win._tech_thread, win._tech_worker, timeout_ms=3000)
    assert ok
    win._tech_thread = None
    win._tech_worker = None
    win.close()
    win.deleteLater()
    qapp.processEvents()
    db.close()


def test_subprocess_close_while_worker_exit_code(tmp_path: Path) -> None:
    """Process enfant Windows : fermeture après stop → rc attendu 0 (pas 0xC0000409)."""
    script = tmp_path / "close_worker.py"
    script.write_text(
        r"""
import os, sys, time
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication
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
        for _ in range(200):
            if self._c:
                self.failed.emit('c')
                return
            time.sleep(0.02)
        self.finished.emit('ok')

app = QApplication([])
w = W()
t = attach_worker_thread(w)
t.start()
time.sleep(0.15)
ok = shutdown_worker_thread(t, w, timeout_ms=5000)
app.processEvents()
sys.exit(0 if ok else 2)
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get(
        "PYTHONPATH", ""
    )
    p = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Documenter codes anormaux — ne pas les masquer
    u32 = p.returncode & 0xFFFFFFFF
    assert p.returncode == 0, (
        f"rc={p.returncode} u32={u32:#x} stdout={p.stdout[-500:]} stderr={p.stderr[-500:]}"
    )
    assert u32 not in {0xC0000005, 0xC0000409}


def test_wizard_shutdown_background_idle(qapp, tmp_path) -> None:
    from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage

    db = Database(tmp_path / "w.sqlite3")
    db.initialize()
    cfg = AppConfig(
        library_root=str(tmp_path / "lib"),
        jobs_dir=str(tmp_path / "jobs"),
        log_dir=str(tmp_path / "logs"),
        freaccmd_path="",
        preferred_release_country="CA",
        auto_approve_high_confidence=False,
    )
    (tmp_path / "lib").mkdir()
    page = ArchiveWizardPage(cfg, db)
    assert page.shutdown_background_work() is True
    page.close()
    db.close()
