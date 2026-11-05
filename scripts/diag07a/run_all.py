"""Orchestrateur diagnostic AVM-07A — capture tous les codes de sortie processus."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".capture_avm07a"
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable


def run(name: str, argv: list[str], timeout: int = 300, env_extra: dict | None = None) -> dict:
    import os

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    t0 = time.perf_counter()
    try:
        p = subprocess.run(argv, cwd=str(ROOT), timeout=timeout, env=env)
        code = p.returncode
    except subprocess.TimeoutExpired:
        code = -9
    dt = time.perf_counter() - t0
    u = code & 0xFFFFFFFF if isinstance(code, int) else None
    klass = "OK"
    if u == 0xC0000005:
        klass = "ACCESS_VIOLATION"
    elif u == 0xC0000409:
        klass = "STACK_BUFFER_OVERRUN"
    elif code not in (0, None):
        klass = f"OTHER_{u:#x}" if u is not None else "OTHER"
    row = {"name": name, "returncode": code, "u32": u, "class": klass, "seconds": round(dt, 3)}
    print(f"{klass:20} {name} rc={code} {dt:.1f}s", flush=True)
    return row


def main() -> int:
    rows = []
    rows.append(run("isolate_crash", [PY, "-X", "faulthandler", str(ROOT / "scripts/diag07a/isolate_crash.py")]))
    rows.append(run("app_lifecycle", [PY, "-X", "faulthandler", str(ROOT / "scripts/diag07a/app_lifecycle.py")], timeout=120))
    rows.append(run("repro_matrix", [PY, str(ROOT / "scripts/diag07a/repro_matrix.py")], timeout=900))

    # Shutdown focus: pytest UI then immediate exit (no junit)
    off = {"QT_QPA_PLATFORM": "offscreen"}
    for i in range(5):
        rows.append(
            run(
                f"pytest_ux06o_shutdown_r{i+1}",
                [
                    PY,
                    "-X",
                    "faulthandler",
                    "-m",
                    "pytest",
                    "tests/test_ux_06o.py",
                    "-q",
                    "--tb=no",
                ],
                timeout=60,
                env_extra=off,
            )
        )
    for i in range(5):
        rows.append(
            run(
                f"pytest_design06l_shutdown_r{i+1}",
                [
                    PY,
                    "-X",
                    "faulthandler",
                    "-m",
                    "pytest",
                    "tests/test_ui_design_06l.py",
                    "-q",
                    "--tb=no",
                ],
                timeout=60,
                env_extra=off,
            )
        )

    # Non-UI freaccmd tests shutdown
    for i in range(3):
        rows.append(
            run(
                f"pytest_freaccmd_r{i+1}",
                [PY, "-X", "faulthandler", "-m", "pytest", "tests/test_freaccmd.py", "-q", "--tb=no"],
                timeout=60,
            )
        )

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "av": sum(1 for r in rows if r["class"] == "ACCESS_VIOLATION"),
        "ok": sum(1 for r in rows if r["class"] == "OK"),
        "other": sum(1 for r in rows if r["class"] not in {"OK", "ACCESS_VIOLATION"}),
    }
    path = OUT / "orchestrator.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("wrote", path)
    print(f"OK={payload['ok']} AV={payload['av']} OTHER={payload['other']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
