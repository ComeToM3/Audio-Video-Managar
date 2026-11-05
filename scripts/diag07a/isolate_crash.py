"""AVM-07A — isolement : freaccmd / MainWindow / GC / import discid."""

from __future__ import annotations

import faulthandler
import gc
import json
import os
import subprocess
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


def step(name: str, fn) -> dict:
    t0 = time.perf_counter()
    row = {"name": name}
    try:
        row["result"] = fn()
        row["status"] = "ok"
    except Exception as exc:  # noqa: BLE001
        row["status"] = "exception"
        row["error"] = str(exc)
        row["trace"] = traceback.format_exc()
    row["seconds"] = round(time.perf_counter() - t0, 3)
    print(f"{row['status']:10} {name} {row['seconds']}s", flush=True)
    return row


def main() -> int:
    rows = []

    def freaccmd_x5():
        exe = Path(r"C:\Program Files\freac\freaccmd.exe")
        codes = []
        for _ in range(5):
            p = subprocess.run(
                [str(exe), "--list-drives"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            codes.append(p.returncode)
        return {"returncodes": codes, "stdout_len": len(p.stdout or "")}

    rows.append(step("freaccmd_list_drives_x5", freaccmd_x5))

    def probe_via_avm():
        from audio_video_manager.extraction.cd import probe_freaccmd
        from audio_video_manager.extraction.cd_ripper import FreacCdRipper

        st = probe_freaccmd(
            configured_path=r"C:\Program Files\freac\freaccmd.exe",
            run_probes=False,
        )
        drives = FreacCdRipper(st.path).list_drives() if st.found and st.path else []
        return {"found": st.found, "n_drives": len(drives)}

    rows.append(step("avm_list_drives", probe_via_avm))

    def import_discid_path():
        from audio_video_manager.metadata.libdiscid_loader import (
            find_discid_dll,
            import_discid,
            prepare_libdiscid_search_path,
        )

        dll = find_discid_dll()
        prepare_libdiscid_search_path()
        mod = import_discid()
        return {"dll": str(dll) if dll else None, "default_device": mod.get_default_device()}

    rows.append(step("import_discid", import_discid_path))

    # Qt offscreen MainWindow create/destroy + GC
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    def qt_mainwindow_cycles():
        from PySide6.QtWidgets import QApplication

        from audio_video_manager.config import AppConfig
        from audio_video_manager.storage import Database
        from audio_video_manager.ui.main_window import MainWindow
        from audio_video_manager.ui.theme import apply_app_style

        app = QApplication.instance() or QApplication([])
        apply_app_style(app)
        notes = []
        for i in range(8):
            tmp = OUT / f"iso_mw_{i}"
            tmp.mkdir(exist_ok=True)
            dbp = tmp / "db.sqlite3"
            if dbp.exists():
                dbp.unlink()
            db = Database(dbp)
            db.initialize()
            cfg = AppConfig(
                library_root=str(tmp / "lib"),
                jobs_dir=str(tmp / "jobs"),
                log_dir=str(tmp / "logs"),
                freaccmd_path=r"C:\Program Files\freac\freaccmd.exe",
                preferred_release_country="CA",
                auto_approve_high_confidence=False,
            )
            (tmp / "lib").mkdir(exist_ok=True)
            win = MainWindow(cfg, db)
            win.show()
            app.processEvents()
            win.navigate_to(1)
            app.processEvents()
            win.close()
            win.deleteLater()
            app.processEvents()
            db.close()
            del win
            del db
            gc.collect()
            app.processEvents()
            notes.append(i)
        return {"cycles": notes, "platform": QApplication.platformName()}

    rows.append(step("qt_mainwindow_x8_gc", qt_mainwindow_cycles))

    def qt_wizard_only_gc():
        from PySide6.QtWidgets import QApplication

        from audio_video_manager.config import AppConfig
        from audio_video_manager.storage import Database
        from audio_video_manager.ui.wizard.archive_wizard import ArchiveWizardPage

        app = QApplication.instance() or QApplication([])
        notes = []
        for i in range(8):
            tmp = OUT / f"iso_wiz_{i}"
            tmp.mkdir(exist_ok=True)
            dbp = tmp / "w.sqlite3"
            if dbp.exists():
                dbp.unlink()
            db = Database(dbp)
            db.initialize()
            cfg = AppConfig(
                library_root=str(tmp / "lib"),
                jobs_dir=str(tmp / "jobs"),
                log_dir=str(tmp / "logs"),
                freaccmd_path=r"C:\Program Files\freac\freaccmd.exe",
                preferred_release_country="CA",
                auto_approve_high_confidence=False,
            )
            page = ArchiveWizardPage(cfg, db)
            app.processEvents()
            page.close()
            page.deleteLater()
            app.processEvents()
            db.close()
            del page
            del db
            gc.collect()
            notes.append(i)
        return {"cycles": notes}

    rows.append(step("qt_wizard_x8_gc", qt_wizard_only_gc))

    def history_card_teardown():
        """Repro pattern 06N SelectableJobCard + clear."""
        from datetime import datetime, timezone as tz

        from PySide6.QtWidgets import QApplication

        from audio_video_manager.storage import Database
        from audio_video_manager.ui.sections.history_page import HistoryPage, SelectableJobCard

        app = QApplication.instance() or QApplication([])
        for i in range(5):
            tmp = OUT / f"iso_hist_{i}"
            tmp.mkdir(exist_ok=True)
            dbp = tmp / "h.sqlite3"
            if dbp.exists():
                dbp.unlink()
            db = Database(dbp)
            db.initialize()
            now = datetime.now(tz.utc).replace(microsecond=0).isoformat()
            conn = db.connect()
            conn.execute(
                """
                INSERT INTO jobs(id, state, step, workdir, started_at, updated_at, finished_at,
                    error_summary, mode, publish_allowed, library_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (f"h{i}", "Completed", "Completed", None, now, now, now, None, "normal", 1, None),
            )
            conn.commit()
            page = HistoryPage(db)
            page.refresh()
            app.processEvents()
            for j in range(page.list.count()):
                w = page.list.itemWidget(page.list.item(j))
                if isinstance(w, SelectableJobCard):
                    w._on_select = lambda _row: None  # noqa: SLF001
            page.list.clear()
            page.close()
            page.deleteLater()
            app.processEvents()
            db.close()
            del page
            gc.collect()
        return {"ok": True}

    rows.append(step("history_card_teardown_x5", history_card_teardown))

    # Forcer GC agressif en fin
    def final_gc():
        for _ in range(5):
            gc.collect()
        return {"collected": True}

    rows.append(step("final_gc_x5", final_gc))

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "all_ok": all(r["status"] == "ok" for r in rows),
    }
    path = OUT / "isolate_crash.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", path, "all_ok=", payload["all_ok"])
    # Exit cleanly without relying on interpreter teardown of Qt
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    # Exit via os._exit after writing to avoid interpreter shutdown crash masking results
    code = main()
    # Small delay for file flush
    time.sleep(0.05)
    # Intentionally use normal exit first so we can observe shutdown crashes in wrapper
    raise SystemExit(code)
