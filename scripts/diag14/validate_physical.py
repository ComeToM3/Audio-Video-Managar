"""Exercise the DVD archive UI against an explicitly authorized source."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def volume_label(source: Path) -> str:
    label = ctypes.create_unicode_buffer(256)
    if not ctypes.windll.kernel32.GetVolumeInformationW(
        str(source), label, len(label), None, None, None, None, 0
    ):
        raise OSError("Impossible de vérifier l'identité du volume source.")
    return label.value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("mkv", "mka"), required=True)
    parser.add_argument("--ifo-sha256", required=True)
    parser.add_argument("--volume-label")
    parser.add_argument("--rights-attested", action="store_true", required=True)
    parser.add_argument("--allow-pcm-conversion", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not args.rights_attested:
        raise ValueError("Une attestation explicite est requise.")
    if args.volume_label is not None and volume_label(source) != args.volume_label:
        raise ValueError("Le volume présent n'est pas le volume confirmé.")
    digest = hashlib.sha256((source / "VIDEO_TS" / "VIDEO_TS.IFO").read_bytes()).hexdigest()
    if digest.lower() != args.ifo_sha256.lower():
        raise ValueError("La structure source ne correspond pas à celle confirmée.")
    if not output.is_dir():
        raise ValueError("Le dossier de destination doit exister.")
    destination = output / f"avm14-master.{args.mode}"
    evidence_file = output / f"avm14-{args.mode}-evidence.json"
    if destination.exists() or evidence_file.exists():
        raise FileExistsError("Destination ou preuve déjà existante; aucun écrasement.")

    local = Path(os.environ["LOCALAPPDATA"])
    backend = local / "Temp" / "AVM-11B2"
    binary_dir = backend / "ffmpeg/unpacked/ffmpeg-9.0.2-full_build/bin"
    navigation_dir = backend / "msys64/ucrt64/bin"
    system_root = Path(os.environ["SystemRoot"])
    for directory in (binary_dir, output, system_root, system_root / "System32"):
        if (directory / "libdvdcss-2.dll").exists():
            raise RuntimeError(f"DLL CSS interdite dans {directory}")
    os.environ["PATH"] = os.pathsep.join((str(binary_dir), str(system_root / "System32")))
    os.environ["PYTHONPATH"] = str(ROOT)
    os.environ["AVM_DATA_DIR"] = str(output / "data")
    os.environ["AVM_LIBRARY_ROOT"] = str(output)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    for name in ("AVM_FFMPEG", "AVM_FFPROBE", "AVM_DVDNAV_DIR", "AVM_10E_MODE"):
        os.environ.pop(name, None)
    os.chdir(output)

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from audio_video_manager.config import AppConfig
    from audio_video_manager.storage import Database
    from audio_video_manager.ui.main_window import MainWindow
    from audio_video_manager.ui.theme import apply_app_style

    app = QApplication([])
    apply_app_style(app)
    config = AppConfig(
        library_root=str(output), jobs_dir=str(output / "jobs"),
        log_dir=str(output / "logs"), library_ui_mode="widgets",
        ffmpeg_path=str(binary_dir / "ffmpeg.exe"), dvdnav_library_dir=str(navigation_dir),
    )
    database = Database(output / "avm14-test.sqlite3")
    database.initialize()
    window = MainWindow(config, database)
    window.show()
    app.processEvents()
    wizard = window.wizard
    wizard.media_combo.setCurrentIndex(1)
    panel = wizard.dvd
    panel.source_combo.setEditText(str(source))
    evidence = {"source": str(source), "ifo_sha256": digest, "mode": args.mode,
                "destination": str(destination), "progress": [], "confirmation": None}

    def wait_for_worker(timeout: float) -> None:
        deadline = time.monotonic() + timeout
        last_report = 0.0
        while wizard.is_busy() and time.monotonic() < deadline:
            app.processEvents()
            now = time.monotonic()
            if now - last_report >= 10:
                entry = {"seconds": round(now - started, 1), "value": panel.progress.value(),
                         "status": panel.status_label.text()}
                evidence["progress"].append(entry)
                print(json.dumps(entry, ensure_ascii=True), flush=True)
                last_report = now
            time.sleep(0.05)
        if wizard.is_busy():
            panel._cancel_or_close()
            if not panel.shutdown_background_work(timeout_ms=12000):
                raise TimeoutError("Le worker ne s'est pas arrêté après annulation.")
            raise TimeoutError("Délai de validation dépassé; annulation demandée.")
        app.processEvents()

    started = time.monotonic()
    try:
        panel.btn_inspect.click()
        wait_for_worker(90)
        if panel._inspection is None:
            raise RuntimeError(panel.status_label.text())
        wizard.btn_next.click()
        if wizard.current_step() != 1:
            raise RuntimeError(panel.status_label.text())
        panel.btn_probe_title.click()
        wait_for_worker(90)
        if panel._title_inspection is None:
            raise RuntimeError(panel.status_label.text())
        evidence["title"] = panel.title_combo.currentText()
        evidence["streams"] = panel.stream_summary.text()
        evidence["chapters"] = [panel.chapter_list.item(index).text() for index in range(panel.chapter_list.count())]
        evidence["audio"] = [panel.audio_list.item(index).text() for index in range(panel.audio_list.count())]
        window.grab().save(str(output / f"avm14-{args.mode}-titres.png"))
        wizard.btn_next.click()
        if wizard.current_step() != 2:
            raise RuntimeError(panel.status_label.text())
        if args.mode == "mka":
            panel.radio_audio.setChecked(True)
            if not panel.audio_list.count():
                raise RuntimeError("Aucune piste audio exploitable pour MKA.")
            panel.audio_list.item(0).setCheckState(Qt.CheckState.Checked)
        if args.allow_pcm_conversion:
            panel.pcm_check.setChecked(True)
        panel.destination_edit.setText(str(destination))
        panel.rights_check.setChecked(True)
        wizard.btn_next.click()
        if wizard.current_step() != 3:
            raise RuntimeError(panel.status_label.text())

        def confirm() -> None:
            for widget in app.topLevelWidgets():
                if isinstance(widget, QMessageBox) and widget.isVisible():
                    evidence["confirmation"] = widget.text()
                    button = widget.button(QMessageBox.StandardButton.Yes)
                    if str(destination) in widget.text() and button is not None:
                        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                    else:
                        widget.reject()
                    return

        QTimer.singleShot(100, confirm)
        wizard.btn_next.click()
        wait_for_worker(4 * 3600)
        evidence["status"] = panel.status_label.text()
        evidence["step"] = wizard.current_step()
        evidence["output_exists"] = destination.is_file()
        evidence["output_bytes"] = destination.stat().st_size if destination.is_file() else None
        evidence["elapsed_seconds"] = round(time.monotonic() - started, 2)
        window.grab().save(str(output / f"avm14-{args.mode}-resultat.png"))
        if wizard.current_step() != 4 or not destination.is_file():
            raise RuntimeError(panel.status_label.text())
        print("RESULT " + json.dumps(evidence, ensure_ascii=True), flush=True)
        return 0
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        print("ERROR " + json.dumps(evidence, ensure_ascii=True), flush=True)
        return 1
    finally:
        with evidence_file.open("x", encoding="utf-8") as file:
            json.dump(evidence, file, ensure_ascii=True, indent=2)
        window.close()
        app.processEvents()
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())