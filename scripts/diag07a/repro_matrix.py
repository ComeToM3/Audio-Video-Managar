"""AVM-07A — matrice de reproduction 0xC0000005 (lecture seule / scripts diag)."""

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

ACCESS_VIOLATION = {3221225477, -1073741819}  # 0xC0000005
STACK_BUFFER = {3221226505, -1073740791}  # 0xC0000409 STATUS_STACK_BUFFER_OVERRUN


def _classify(code: int) -> str:
    u = code & 0xFFFFFFFF
    if u in {0xC0000005}:
        return "ACCESS_VIOLATION"
    if u in {0xC0000409}:
        return "STACK_BUFFER_OVERRUN"
    if code == 0:
        return "OK"
    if code < 0:
        return f"NEG_{u:#x}"
    return f"EXIT_{code}"


def run_once(name: str, argv: list[str], *, env: dict | None = None, timeout: int = 180) -> dict:
    e = os.environ.copy()
    if env:
        e.update(env)
    # Ne jamais forcer offscreen ici sauf si déjà dans env du scénario
    t0 = time.perf_counter()
    try:
        p = subprocess.run(
            argv,
            cwd=str(ROOT),
            env=e,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        code = p.returncode
        out = (p.stdout or "")[-4000:]
        err = (p.stderr or "")[-4000:]
    except subprocess.TimeoutExpired as exc:
        code = -9
        out = ((exc.stdout or b"") if isinstance(exc.stdout, (bytes, bytearray)) else (exc.stdout or ""))
        err = ((exc.stderr or b"") if isinstance(exc.stderr, (bytes, bytearray)) else (exc.stderr or ""))
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")[-4000:]
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")[-4000:]
    dt = time.perf_counter() - t0
    row = {
        "name": name,
        "argv": argv[1:],
        "returncode": code,
        "returncode_u32": code & 0xFFFFFFFF if isinstance(code, int) else None,
        "class": _classify(code if isinstance(code, int) else -1),
        "seconds": round(dt, 3),
        "stdout_tail": out,
        "stderr_tail": err,
    }
    print(
        f"[{row['class']:20}] {name:40} rc={code} ({row['returncode_u32']:#x}) {dt:.1f}s",
        flush=True,
    )
    return row


def main() -> int:
    py = sys.executable
    faulthandler_cmd = [
        "-X",
        "faulthandler",
        "-c",
        "import faulthandler; faulthandler.enable(all_threads=True); "
        "import pytest; raise SystemExit(pytest.main(%r))",
    ]

    scenarios: list[tuple[str, list[str], dict | None]] = []

    # --- Suite complète ---
    for i in range(3):
        scenarios.append(
            (
                f"full_suite_r{i+1}",
                [py, "-X", "faulthandler", "-m", "pytest", "tests/", "-q", "--tb=no"],
                {"QT_QPA_PLATFORM": "offscreen"},
            )
        )

    # --- UI isolés ---
    ui_files = [
        "tests/test_ux_06o.py",
        "tests/test_ui_design_06l.py",
        "tests/test_ui_shell.py",
        "tests/test_ui_library_history_06h.py",
        "tests/test_history_06n.py",
        "tests/test_ui_w3_prefill.py",
    ]
    for f in ui_files:
        scenarios.append(
            (
                f"ui_file_{Path(f).stem}",
                [py, "-X", "faulthandler", "-m", "pytest", f, "-q", "--tb=line"],
                {"QT_QPA_PLATFORM": "offscreen"},
            )
        )

    # --- Non-UI ---
    scenarios.append(
        (
            "non_ui_batch",
            [
                py,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_duplicates_06k.py",
                "tests/test_archive_pipeline.py",
                "tests/test_freaccmd.py",
                "-q",
                "--tb=no",
            ],
            {"QT_QPA_PLATFORM": "offscreen"},
        )
    )

    # --- freaccmd seul (pas Qt) ---
    freac = Path(r"C:\Program Files\freac\freaccmd.exe")
    if freac.is_file():
        for i in range(5):
            scenarios.append(
                (
                    f"freaccmd_list_drives_r{i+1}",
                    [str(freac), "--list-drives"],
                    None,
                )
            )

    # --- Séquences ordre UI ---
    scenarios.append(
        (
            "ui_order_shell_then_06o",
            [
                py,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ui_shell.py",
                "tests/test_ux_06o.py",
                "-q",
                "--tb=line",
            ],
            {"QT_QPA_PLATFORM": "offscreen"},
        )
    )
    scenarios.append(
        (
            "ui_order_06o_then_shell",
            [
                py,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ux_06o.py",
                "tests/test_ui_shell.py",
                "-q",
                "--tb=line",
            ],
            {"QT_QPA_PLATFORM": "offscreen"},
        )
    )
    scenarios.append(
        (
            "ui_order_design_shell_06o",
            [
                py,
                "-X",
                "faulthandler",
                "-m",
                "pytest",
                "tests/test_ui_design_06l.py",
                "tests/test_ui_shell.py",
                "tests/test_ux_06o.py",
                "-q",
                "--tb=line",
            ],
            {"QT_QPA_PLATFORM": "offscreen"},
        )
    )

    rows = []
    for name, argv, env in scenarios:
        rows.append(run_once(name, argv, env=env))

    summary = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "rows": rows,
        "access_violation_count": sum(1 for r in rows if r["class"] == "ACCESS_VIOLATION"),
        "stack_buffer_count": sum(1 for r in rows if r["class"] == "STACK_BUFFER_OVERRUN"),
        "ok_count": sum(1 for r in rows if r["class"] == "OK"),
    }
    path = OUT / "repro_matrix.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(
        f"OK={summary['ok_count']} AV={summary['access_violation_count']} "
        f"STACK={summary['stack_buffer_count']} total={len(rows)}"
    )
    print("wrote", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
