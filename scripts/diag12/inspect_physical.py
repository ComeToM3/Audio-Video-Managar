"""Read-only physical DVD inspection; no extraction, decoding, or CSS backend."""

from __future__ import annotations

import argparse
from dataclasses import asdict
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = Path(args.source)
    local = Path(os.environ["LOCALAPPDATA"])
    backend = local / "Temp/AVM-11B2"
    binary_dir = backend / "ffmpeg/unpacked/ffmpeg-9.0.2-full_build/bin"
    navigation_dir = backend / "msys64/ucrt64/bin"
    profile = Path(tempfile.mkdtemp(prefix="AVM-12-", dir=local / "Temp"))
    personal = local / "AudioVideoManager/config.json"
    before = hashlib.sha256(personal.read_bytes()).hexdigest() if personal.is_file() else None
    os.environ["AVM_DATA_DIR"] = str(profile / "data")
    os.environ["AVM_LIBRARY_ROOT"] = str(profile / "library")
    os.environ["PATH"] = os.pathsep.join((str(binary_dir), str(Path(os.environ["SystemRoot"]) / "System32")))
    for variable in ("AVM_FFMPEG", "AVM_FFPROBE", "AVM_DVDNAV_DIR", "AVM_10E_MODE"):
        os.environ.pop(variable, None)
    os.chdir(profile)
    search_dirs = (binary_dir, profile, Path(os.environ["SystemRoot"]), Path(os.environ["SystemRoot"]) / "System32")
    for directory in search_dirs:
        assert not (directory / "libdvdcss-2.dll").exists(), str(directory)

    from audio_video_manager.extraction.dvd import DvdInspector
    from audio_video_manager.extraction.dvd_navigation import DvdNavigator
    from audio_video_manager.metadata.video import VideoInspectionStatus

    native_files = []
    for name in ("libdvdnav-4.dll", "libdvdread-8.dll"):
        path = navigation_dir / name
        native_files.append({"name": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    navigator = DvdNavigator(navigation_dir, timeout_seconds=30)
    calls = []
    original_run = subprocess.run

    def capture(argv, **kwargs):
        started = time.monotonic()
        try:
            result = original_run(argv, **kwargs)
        except (OSError, subprocess.TimeoutExpired) as exc:
            calls.append({"argv": argv, "error": str(exc), "duration_seconds": time.monotonic() - started})
            raise
        calls.append({"argv": argv, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "duration_seconds": time.monotonic() - started})
        return result

    inspector = DvdInspector(binary_dir / "ffprobe.exe", runner=capture, navigator=navigator, timeout_seconds=30)
    video_ts = source / "VIDEO_TS"
    with (video_ts / "VIDEO_TS.IFO").open("rb") as file:
        header = file.read(12).decode("ascii", errors="replace")
    structure = [{"name": path.name, "size": path.stat().st_size} for path in sorted(video_ts.glob("*.IFO"))]
    inspections = []
    subprocess.run = capture
    try:
        started = time.monotonic()
        enumeration = inspector.inspect(source)
        inspections.append({"operation": "enumeration", "duration_seconds": time.monotonic() - started, "result": asdict(enumeration)})
        if enumeration.status == VideoInspectionStatus.TITLE_SELECTION_REQUIRED:
            for candidate in enumeration.title_candidates:
                for angle in range(1, (candidate.angle_count or 1) + 1):
                    started = time.monotonic()
                    result = inspector.inspect(source, title_indices=(candidate.title_index,), angle_index=angle)
                    inspections.append({"operation": "title", "title_index": candidate.title_index, "angle_index": angle, "duration_seconds": time.monotonic() - started, "result": asdict(result)})
    finally:
        subprocess.run = original_run
    after = hashlib.sha256(personal.read_bytes()).hexdigest() if personal.is_file() else None
    evidence = {"source": str(source), "profile": str(profile), "source_header": header, "ifo_files": structure, "native_files": native_files, "css_dll_search_dirs": [str(directory) for directory in search_dirs], "calls": calls, "inspections": inspections, "personal_config_before": before, "personal_config_after": after, "extractions": [], "rights": "inspection only; reproduction not established"}
    target = ROOT / "docs/architecture/reports/AVM-12-evidence/physical-inspection.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")
    assert before == after
    for item in inspections:
        result = item["result"]
        print(json.dumps({"operation": item["operation"], "seconds": item["duration_seconds"], "status": result["status"], "diagnostic": result["diagnostic"], "detail": result["technical_detail"], "candidates": len(result["title_candidates"]), "titles": result["titles"]}, default=str))
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())