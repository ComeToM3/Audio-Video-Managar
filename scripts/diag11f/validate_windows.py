"""Native Windows settings persistence and DVD dependency checks in a Temp profile."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def phase(name: str, profile: Path) -> dict:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea

    from audio_video_manager.config import load_config
    from audio_video_manager.paths import default_config_path
    from audio_video_manager.ui.dvd_extraction_dialog import DvdArchivePanel
    from audio_video_manager.ui.dvd_worker import DvdTaskWorker
    from audio_video_manager.ui.sections.settings_page import SettingsPage
    from audio_video_manager.ui.theme import apply_app_style

    local = Path(os.environ["LOCALAPPDATA"])
    backend = local / "Temp" / "AVM-11B2"
    ffmpeg = backend / "ffmpeg/unpacked/ffmpeg-9.0.2-full_build/bin/ffmpeg.exe"
    dvdnav = backend / "msys64/ucrt64/bin"
    source = local / "Temp/AVM-11C/reference-dvd"
    assert ffmpeg.is_file() and source.is_dir()
    app = QApplication([])
    apply_app_style(app)
    config = load_config()
    settings = SettingsPage(config)
    settings.resize(1100, 900)
    settings.show()
    assert QTest.qWaitForWindowExposed(settings, 5000)
    result = {"phase": name, "platform": app.platformName(), "config_path": str(default_config_path())}
    assert app.platformName() == "windows"

    def wait(predicate, seconds=60):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            app.processEvents()
            if predicate():
                return
            QTest.qWait(20)
        raise TimeoutError("Qt worker did not settle")

    if name == "save":
        def replace(edit, value):
            edit.setFocus()
            QTest.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            QTest.keyClicks(edit, str(value))
            assert edit.text() == str(value)

        replace(settings.edit_ffmpeg, ffmpeg)
        replace(settings.edit_dvdnav, dvdnav)
        saved = []
        settings.config_saved.connect(lambda value: saved.append(value.to_dict()))

        def dismiss():
            for widget in app.topLevelWidgets():
                if isinstance(widget, QMessageBox) and widget.isVisible():
                    result["save_message"] = widget.text()
                    QTest.mouseClick(widget.button(QMessageBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
                    return
            QTimer.singleShot(20, dismiss)

        button = next(button for button in settings.findChildren(QPushButton) if button.text() == "Enregistrer")
        settings.findChild(QScrollArea).ensureWidgetVisible(button)
        QTimer.singleShot(20, dismiss)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert len(saved) == 1
        disk = json.loads(default_config_path().read_text(encoding="utf-8"))
        assert disk["ffmpeg_path"] == str(ffmpeg)
        assert disk["dvdnav_library_dir"] == str(dvdnav)
        result["persisted"] = True
        result["paths"] = {key: disk[key] for key in ("ffmpeg_path", "dvdnav_library_dir")}
    else:
        assert settings.edit_ffmpeg.text() == str(ffmpeg)
        assert settings.edit_dvdnav.text() == str(dvdnav)
        result["reloaded_fields"] = True
        worker = DvdTaskWorker(config=config, task="inspect", source=str(source))
        inspector = worker._inspector()
        result["derived_ffprobe"] = str(inspector._find_ffprobe())
        assert inspector._find_ffprobe() == ffmpeg.with_name("ffprobe.exe")
        good = inspector.inspect(source, title_indices=(2,))
        result["inspection"] = {"status": good.status.value, "titles": len(good.title_candidates), "streams": len(good.titles[0].streams) if good.titles else 0}
        assert len(good.title_candidates) == 2 and good.titles
        cases = []
        for label, tool, libraries in (
            ("absent", "", ""),
            ("invalid_path", str(profile / "missing/ffmpeg.exe"), str(dvdnav)),
            ("incompatible_demuxer", r"C:\Tools\ffmpeg\bin\ffmpeg.exe", str(dvdnav)),
            ("missing_dll", str(ffmpeg), str(profile / "missing-dll")),
            ("invalid_executable", str(profile / "invalid-bin/ffmpeg.exe"), str(dvdnav)),
            ("invalid_dll", str(ffmpeg), str(profile / "invalid-dll")),
        ):
            if label == "incompatible_demuxer" and not Path(tool).is_file():
                cases.append({"case": label, "not_tested": "binary absent"})
                continue
            if label == "invalid_executable":
                Path(tool).parent.mkdir()
                Path(tool).write_bytes(b"AVM invalid executable fixture")
                Path(tool).with_name("ffprobe.exe").write_bytes(b"AVM invalid executable fixture")
            if label == "invalid_dll":
                Path(libraries).mkdir()
                for dll in ("libdvdnav-4.dll", "libdvdread-8.dll"):
                    (Path(libraries) / dll).write_bytes(b"AVM invalid DLL fixture")
            scenario = copy.deepcopy(config)
            scenario.ffmpeg_path = tool
            scenario.dvdnav_library_dir = libraries
            dialog = DvdArchivePanel(scenario)
            dialog.show()
            dialog.source_combo.setEditText(str(source))
            QTest.mouseClick(dialog.btn_inspect, Qt.MouseButton.LeftButton)
            wait(lambda: dialog._thread is None)
            message = dialog.status_label.text()
            assert dialog._inspection is None and not dialog.btn_start.isEnabled()
            assert "not defined" not in message
            cases.append({"case": label, "message": message, "start_enabled": dialog.btn_start.isEnabled()})
            dialog.grab().save(str(profile / (label + ".png")))
            dialog.close()
        result["dependency_cases"] = cases
    settings.grab().save(str(profile / (name + "-settings.png")))
    settings.close()
    app.processEvents()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("save", "reload"))
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    if args.phase:
        print(json.dumps(phase(args.phase, args.profile), ensure_ascii=True), flush=True)
        return 0
    local = Path(os.environ["LOCALAPPDATA"])
    profile = Path(tempfile.mkdtemp(prefix="AVM-11F-", dir=local / "Temp"))
    personal = local / "AudioVideoManager/config.json"
    before = digest(personal)
    env = os.environ.copy()
    for key in ("AVM_10E_MODE", "AVM_FFMPEG", "AVM_FFPROBE", "AVM_DVDNAV_DIR"):
        env.pop(key, None)
    env.update(AVM_DATA_DIR=str(profile / "data"), AVM_LIBRARY_ROOT=str(profile / "library"), QT_QPA_PLATFORM="windows", PATH=os.environ["SystemRoot"] + "\\System32")
    results = []
    for name in ("save", "reload"):
        child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--phase", name, "--profile", str(profile)], cwd=ROOT, env=env, text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=150)
        results.append({"phase": name, "returncode": child.returncode, "stdout": child.stdout, "stderr": child.stderr})
        if child.returncode:
            break
    evidence = {"profile": str(profile), "personal_config_before": before, "personal_config_after": digest(personal), "results": results}
    report = ROOT / ".ci/avm11f-native.json"
    report.parent.mkdir(exist_ok=True)
    report.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    assert before == digest(personal)
    return 0 if len(results) == 2 and all(item["returncode"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())