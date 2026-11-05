#!/usr/bin/env python3
"""AVM-10C.2 — matrice exhaustive UI : fermeture naturelle + diagnostics ON."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".ci" / "avm10c2-matrix-natural.json"

# Aligné UI_TEST_FILES / orchestrateur (+ teardown 10C.x)
UI_FILES = [
    "tests/test_history_06n.py",
    "tests/test_ux_06o.py",
    "tests/test_ui_design_06l.py",
    "tests/test_ui_shell.py",
    "tests/test_ui_library_history_06h.py",
    "tests/test_library_qml_08b.py",
    "tests/test_humanisation_06i.py",
    "tests/test_ui_w3_prefill.py",
    "tests/test_ui_collision_replace_disabled.py",
    "tests/test_qthread_07b.py",
    "tests/test_qt_teardown_10c1.py",
    "tests/test_qt_teardown_10c2.py",
]


def classify(rc: int) -> str:
    u = rc & 0xFFFFFFFF
    if rc == 0:
        return "PASS_REAL"
    if u == 0xC0000005 or rc in (-1073741819, 139):
        return "NATIVE_CRASH_0xC0000005"
    if u == 0xC0000409 or rc in (-1073740791,):
        return "NATIVE_CRASH_0xC0000409"
    if rc != 0:
        return f"FAIL_rc_{rc}"
    return "UNKNOWN"


def run_one(path: str) -> dict:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    env["AVM_QT_SAFE_EXIT"] = "0"
    env["PYTHONFAULTHANDLER"] = "1"
    junit = ROOT / ".ci" / "avm10c2-junit" / f"{Path(path).stem}_natural.xml"
    junit.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable,
        "-X",
        "faulthandler",
        "-m",
        "pytest",
        path,
        "-q",
        "--tb=line",
        f"--junitxml={junit}",
        # Diagnostics ON : remplace addopts qui coupe unraisableexception
        "-o",
        "addopts=-q",
    ]
    t0 = time.perf_counter()
    proc = subprocess.run(argv, cwd=str(ROOT), env=env, capture_output=True, text=True)
    dur = round(time.perf_counter() - t0, 3)
    rc = int(proc.returncode)
    err = (proc.stderr or "") + (proc.stdout or "")
    note = ""
    if "access violation" in err.lower():
        note = "faulthandler:access_violation"
    if "Fatal Python error" in err:
        note = (note + "; " if note else "") + "fatal_python"
    return {
        "file": path,
        "returncode": rc,
        "duration_sec": dur,
        "classification": classify(rc),
        "junit": str(junit.relative_to(ROOT)),
        "note": note,
        "safe_exit": False,
        "unraisableexception": True,
    }


def main() -> int:
    cells = []
    for path in UI_FILES:
        if not (ROOT / path).is_file():
            cells.append(
                {
                    "file": path,
                    "returncode": None,
                    "classification": "NOT_TESTED_missing",
                    "safe_exit": False,
                    "unraisableexception": True,
                }
            )
            continue
        print(f"RUN {path} ...", flush=True)
        cell = run_one(path)
        cells.append(cell)
        print(f"  -> rc={cell['returncode']} {cell['classification']}", flush=True)

    go = all(c.get("classification") == "PASS_REAL" for c in cells)
    payload = {
        "policy": {
            "AVM_QT_SAFE_EXIT": "0",
            "unraisableexception": "enabled via -o addopts=-q",
            "os._exit": False,
        },
        "cells": cells,
        "summary": {
            "total": len(cells),
            "pass_real": sum(1 for c in cells if c.get("classification") == "PASS_REAL"),
            "fail": sum(1 for c in cells if c.get("classification") != "PASS_REAL"),
            "go": go,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {OUT}")
    return 0 if go else 2


if __name__ == "__main__":
    raise SystemExit(main())
