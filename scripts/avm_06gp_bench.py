"""
Banc AVM-06G-P — mesures reproductibles (sans rip optique, sans toucher Queen).

Usage:
  python scripts/avm_06gp_bench.py

Lit les 17 FLAC du job bd40 (zone A) en lecture seule ; écrit sous %TEMP%/avm-06gp-bench.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audio_video_manager.diagnostics.perf import PerfSession
from audio_video_manager.library.transfer import transfer_file
from audio_video_manager.metadata.factories import make_approvable_sheet
from audio_video_manager.metadata.validation import approve_sheet
from audio_video_manager.library.publish import CollisionPolicy
from audio_video_manager.orchestration.archive_job import run_archive_job
from audio_video_manager.storage import Database
from audio_video_manager.verification.flac_decode import decode_many, find_flac_decode_tool
from audio_video_manager.verification.flac_integrity import check_many

BD40_RIP = Path(
    os.environ.get(
        "AVM_06GP_FLAC_DIR",
        r"C:\Users\ComeToM3\AppData\Local\AudioVideoManager\jobs"
        r"\bd40b604b7a147b985916f9f97f70223\rip",
    )
)
OUT = Path(os.environ.get("TEMP", "/tmp")) / "avm-06gp-bench"
REPORT_JSON = ROOT / "docs" / "ux" / "reports" / "AVM-06G-P-bench.json"


def _env() -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "ffmpeg": str(find_flac_decode_tool()),
        "flac_source": str(BD40_RIP),
        "bench_root": str(OUT),
    }


def micro_transfer(flacs: list[Path]) -> dict:
    total = sum(p.stat().st_size for p in flacs)
    results = {}
    for mode in ("copy", "auto"):
        dest_root = OUT / f"xfer_{mode}"
        if dest_root.exists():
            shutil.rmtree(dest_root)
        dest_root.mkdir(parents=True)
        os.environ["AVM_TRANSFER"] = mode
        t0 = time.perf_counter()
        methods: dict[str, int] = {}
        for p in flacs:
            m = transfer_file(p, dest_root / p.name)
            methods[m] = methods.get(m, 0) + 1
        dt = time.perf_counter() - t0
        results[mode] = {
            "seconds": round(dt, 4),
            "bytes": total,
            "mb_per_s": round((total / 1e6) / dt, 2) if dt > 0 else None,
            "methods": methods,
        }
    os.environ.pop("AVM_TRANSFER", None)
    return results


def integrity_and_decode(flacs: list[Path]) -> dict:
    perf = PerfSession(label="verify")
    with perf.span("f08a", items=len(flacs), bytes_in=sum(p.stat().st_size for p in flacs)):
        integrity = check_many(flacs)
    with perf.span("decode", items=len(flacs), bytes_in=sum(p.stat().st_size for p in flacs)):
        decoded = decode_many(flacs)
    return {
        "integrity_ok": all(i.ok for i in integrity),
        "decode_attempted": bool(decoded and decoded[0].attempted),
        "decode_ok": all((not d.attempted) or d.ok for d in decoded),
        "perf": perf.summary(),
    }


def pipeline(flacs: list[Path], *, mode: str, tracks: int | None = None) -> dict:
    os.environ["AVM_TRANSFER"] = mode
    n = tracks or len(flacs)
    use = flacs[:n]
    sheet = make_approvable_sheet(tracks=n)
    # aligner titres génériques ; numéros 1..n
    approve_sheet(sheet, note="bench")
    run_root = OUT / f"pipeline_{mode}"
    if run_root.exists():
        shutil.rmtree(run_root)
    jobs = run_root / "jobs"
    lib = run_root / "Music"
    db = Database(run_root / "bench.sqlite3")
    db.initialize()
    t0 = time.perf_counter()
    report = run_archive_job(
        metadata=sheet,
        library_root=lib,
        jobs_root=jobs,
        db=db,
        confirm_publish=True,
        collision_policy=CollisionPolicy.RENAME,
        staged_flac_files=use,
        cover_bytes=None,
        skip_disc_match=True,
    )
    wall = time.perf_counter() - t0
    os.environ.pop("AVM_TRANSFER", None)
    return {
        "mode": mode,
        "state": report.state,
        "wall_seconds": round(wall, 4),
        "perf": report.perf,
        "tracks": n,
    }


def main() -> int:
    if not BD40_RIP.is_dir():
        print("FLAC source missing:", BD40_RIP, file=sys.stderr)
        return 2
    flacs = sorted(BD40_RIP.glob("*.flac"))
    if len(flacs) < 17:
        print(f"expected 17 flacs, got {len(flacs)}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "env": _env(),
        "album_bytes": sum(p.stat().st_size for p in flacs),
        "track_count": len(flacs),
        "micro_transfer": micro_transfer(flacs),
        "verify": integrity_and_decode(flacs),
        # Pipeline complet 17 pistes : copy forcé vs auto (hardlink)
        "pipeline_copy": pipeline(flacs, mode="copy"),
        "pipeline_auto": pipeline(flacs, mode="auto"),
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("Wrote", REPORT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
