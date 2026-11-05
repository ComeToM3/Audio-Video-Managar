#!/usr/bin/env python3
"""AVM-10C.1 — deux vrais processus Windows sur verrous recovery + PID identity."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".ci" / "avm10c1-two-process-locks.json"

CHILD_HOLD = """
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, r"{root}")
from audio_video_manager.orchestration.rip_lock import (
    try_acquire_recovery_file_lock, release_recovery_file_lock, write_rip_lock, read_rip_lock, is_lock_holder_active
)
lock_dir = Path(sys.argv[1])
rip = Path(sys.argv[2])
ready = Path(sys.argv[3])
hold_sec = float(sys.argv[4])
got = try_acquire_recovery_file_lock(lock_dir, job_id="child-proc")
write_rip_lock(rip, job_id="child-rip")
info = read_rip_lock(rip)
ready.write_text(json.dumps({{
    "recovery_acquired": got is not None,
    "pid": os.getpid(),
    "rip_active": bool(info and is_lock_holder_active(info)),
    "create_time": info.create_time if info else None,
}}), encoding="utf-8")
time.sleep(hold_sec)
release_recovery_file_lock(lock_dir, job_id="child-proc")
from audio_video_manager.orchestration.rip_lock import clear_rip_lock
clear_rip_lock(rip)
print("child_done")
"""


def main() -> int:
    from audio_video_manager.orchestration.rip_lock import (
        is_lock_holder_active,
        read_rip_lock,
        try_acquire_recovery_file_lock,
        write_rip_lock,
        clear_rip_lock,
        LOCK_FILENAME,
    )

    tmp = Path(tempfile.mkdtemp(prefix="avm10c1_locks_"))
    lock_dir = tmp / "jobs"
    rip = tmp / "job" / "rip"
    rip.mkdir(parents=True)
    ready = tmp / "ready.json"
    hold = 3.0

    script = tmp / "child.py"
    script.write_text(CHILD_HOLD.format(root=str(ROOT)), encoding="utf-8")
    child = subprocess.Popen(
        [sys.executable, str(script), str(lock_dir), str(rip), str(ready), str(hold)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Wait ready
    for _ in range(50):
        if ready.is_file():
            break
        time.sleep(0.1)
    child_meta = json.loads(ready.read_text(encoding="utf-8")) if ready.is_file() else {}

    # Pendant que l’enfant tient le verrou
    parent_recovery = try_acquire_recovery_file_lock(lock_dir, job_id="parent-proc")
    parent_blocked = parent_recovery is None

    # PID reuse simulation on child's rip lock while child still alive:
    # rewrite create_time to fake while keeping child's PID would require knowing PID —
    # instead: after child exits, leave stale lock with dead pid
    child.wait(timeout=hold + 10)
    # Enfant a clear le rip lock — recréer verrou périmé
    stale = rip / LOCK_FILENAME
    stale.write_text(
        json.dumps(
            {
                "pid": 999_888_777,
                "job_id": "stale",
                "started_at": "2020-01-01T00:00:00+00:00",
                "create_time": 1,
            }
        ),
        encoding="utf-8",
    )
    stale_info = read_rip_lock(rip)
    stale_active = is_lock_holder_active(stale_info)

    # Réutilisation PID simulée : PID du parent + create_time faux
    write_rip_lock(rip, job_id="parent-alive")
    live = read_rip_lock(rip)
    # Forcer mismatch
    data = json.loads((rip / LOCK_FILENAME).read_text(encoding="utf-8"))
    data["create_time"] = 1
    (rip / LOCK_FILENAME).write_text(json.dumps(data), encoding="utf-8")
    reused = read_rip_lock(rip)
    reused_active = is_lock_holder_active(reused)
    clear_rip_lock(rip)

    payload = {
        "child": child_meta,
        "child_returncode": child.returncode,
        "parent_blocked_while_child_holds": parent_blocked,
        "stale_lock_active": stale_active,
        "live_lock_before_tamper_active": bool(live and is_lock_holder_active(live)),
        "reused_pid_lock_active": reused_active,
        "ok": (
            child.returncode == 0
            and child_meta.get("recovery_acquired") is True
            and parent_blocked is True
            and stale_active is False
            and reused_active is False
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
