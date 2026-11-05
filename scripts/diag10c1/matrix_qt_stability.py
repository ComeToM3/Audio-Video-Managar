#!/usr/bin/env python3
"""AVM-10C.1 — matrice comparative Qt / pytest (codes de sortie natifs).

Ne masque rien : conserve faulthandler, rapporte rc bruts et classification.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".ci" / "avm10c1-matrix.json"

UI_SAMPLES = [
    "tests/test_history_06n.py",  # souvent stable
    "tests/test_ux_06o.py",  # AV historique Mode A
    "tests/test_ui_shell.py",  # AV historique
    "tests/test_ui_design_06l.py",
    "tests/test_qthread_07b.py",  # STACK historique
    "tests/test_ui_collision_replace_disabled.py",
]

WIN_AV = 0xC0000005
WIN_STACK = 0xC0000409


@dataclass
class Cell:
    file: str
    safe_exit: bool
    no_unraisable: bool
    returncode: int
    duration_sec: float
    classification: str
    note: str = ""


def classify(rc: int) -> str:
    u = rc & 0xFFFFFFFF
    if rc == 0:
        return "PASS_REAL" if True else "PASS_REAL"
    if u in (WIN_AV, 3221225477) or rc in (-1073741819, 139):
        return "NATIVE_CRASH_0xC0000005"
    if u in (WIN_STACK, 3221226505) or rc in (-1073740791, 127, 137):
        return "NATIVE_CRASH_0xC0000409"
    if rc > 255 and (u & 0xF0000000) == 0xC0000000:
        return f"NATIVE_CRASH_0x{u:08X}"
    if rc != 0:
        return f"PYTEST_FAIL_rc_{rc}"
    return "UNKNOWN"


def run_cell(path: str, *, safe_exit: bool, no_unraisable: bool) -> Cell:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    env["AVM_QT_SAFE_EXIT"] = "1" if safe_exit else "0"
    env["PYTHONFAULTHANDLER"] = "1"
    stem = Path(path).stem
    junit = ROOT / ".ci" / "avm10c1-junit" / (
        f"{stem}_safe{int(safe_exit)}_nou{int(no_unraisable)}.xml"
    )
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
    ]
    # Override pyproject addopts: force unraisable on or off
    if no_unraisable:
        argv.extend(["-p", "no:unraisableexception", "-o", "addopts=-q"])
    else:
        # Explicitly enable plugin — replace pyproject's -p no:unraisableexception
        argv.extend(["-o", "addopts=-q"])
    t0 = time.perf_counter()
    proc = subprocess.run(argv, cwd=str(ROOT), env=env, capture_output=True, text=True)
    dur = round(time.perf_counter() - t0, 3)
    rc = int(proc.returncode)
    cls = classify(rc)
    if safe_exit and rc == 0:
        cls = "PASS_WITH_WORKAROUND"  # os._exit path — not proven natural close
    elif (not safe_exit) and (not no_unraisable) and rc == 0:
        cls = "PASS_REAL"
    elif (not safe_exit) and no_unraisable and rc == 0:
        cls = "PASS_REAL_DIAGNOSTICS_OFF"
    note = f"junit={junit.name}"
    err = (proc.stderr or "") + (proc.stdout or "")
    if "access violation" in err.lower() or "0xC0000005" in err:
        note += "; faulthandler:access_violation"
    if "0xC0000409" in err or "stack buffer" in err.lower():
        note += "; faulthandler:stack"
    if "Windows fatal exception" in err:
        note += "; windows_fatal"
    # Keep last lines of crash context
    if rc != 0 and "faulthandler" not in note:
        tail = " | ".join(err.strip().splitlines()[-4:])[:300]
        if tail:
            note += f"; tail={tail}"
    return Cell(
        file=path,
        safe_exit=safe_exit,
        no_unraisable=no_unraisable,
        returncode=rc,
        duration_sec=dur,
        classification=cls,
        note=note,
    )


def main() -> int:
    cells: list[Cell] = []
    combos = [
        (False, False),  # natural exit, diagnostics ON  ← critère GO
        (False, True),  # natural exit, no unraisable
        (True, True),  # workaround 10C default-ish
        (True, False),  # safe exit but diagnostics plugin on
    ]
    for path in UI_SAMPLES:
        if not (ROOT / path).is_file():
            continue
        for safe, no_u in combos:
            print(f"RUN {path} safe_exit={safe} no_unraisable={no_u} ...", flush=True)
            cell = run_cell(path, safe_exit=safe, no_unraisable=no_u)
            cells.append(cell)
            print(
                f"  -> rc={cell.returncode} {cell.classification} {cell.note}",
                flush=True,
            )

    summary = {
        "pass_real": sum(1 for c in cells if c.classification == "PASS_REAL"),
        "pass_workaround": sum(1 for c in cells if c.classification == "PASS_WITH_WORKAROUND"),
        "native_crash": sum(1 for c in cells if c.classification.startswith("NATIVE_")),
        "other_fail": sum(
            1
            for c in cells
            if c.classification.startswith("PYTEST_") or c.classification == "UNKNOWN"
        ),
        "go_criterion_natural_close": all(
            c.classification == "PASS_REAL"
            for c in cells
            if (not c.safe_exit) and (not c.no_unraisable)
        ),
    }
    payload = {
        "cells": [asdict(c) for c in cells],
        "summary": summary,
        "go_criterion": (
            "Fermeture normale sans crash, sans os._exit, sans -p no:unraisableexception"
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {OUT}")
    return 0 if summary["go_criterion_natural_close"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
